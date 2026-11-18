"""Private offline FastAPI probe: Windows CMD/Linux, no dotenv or cloud access."""
import argparse
import http.client
import os
from pathlib import Path
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (('GET', '/api/health', 200), ('GET', '/api/ready', 503),
          ('GET', '/api/me', 401), ('POST', '/api/resume/upload', 404))


def child_environment():
    # Allow only OS/bootstrap settings. In particular: no HOME/USERPROFILE,
    # PYTHONPATH, proxy credentials, cloud/provider keys or PostgreSQL opt-ins.
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'SYSTEMDRIVE',
               'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE'}
    result = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    result.update(PYTHON_DOTENV_DISABLED='1', CLOUD_ENABLED='false', API_PUBLIC_MODE='false',
                  API_LEGACY_UPLOAD_ENABLED='false', CLOUD_AI_ENABLED='false')
    return result


def child_guards():
    # Keep Windows asyncio's loopback socket pairs working. Block non-loopback
    # destinations and external name resolution before importing the application.
    connect, connect_ex, lookup = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
    def check(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
                raise RuntimeError('External connections blocked in localhost verification.')
    def local_connect(sock, address):
        check(sock, address)
        return connect(sock, address)
    def local_connect_ex(sock, address):
        check(sock, address)
        return connect_ex(sock, address)
    def local_lookup(host, *args, **kwargs):
        if host not in ('127.0.0.1', '::1', 'localhost'):
            raise RuntimeError('External name resolution blocked in localhost verification.')
        return lookup(host, *args, **kwargs)
    socket.socket.connect, socket.socket.connect_ex = local_connect, local_connect_ex
    socket.getaddrinfo = local_lookup
    # Native libpq can bypass Python socket hooks; block DB checkouts separately.
    from sqlalchemy.engine import Engine
    def no_database(engine):
        raise RuntimeError('Database access blocked in localhost verification.')
    Engine.raw_connection = no_database


def serve(port):
    """Internal child only; one worker, no reload, no grandchildren or env files."""
    environment = child_environment()
    os.environ.clear()
    os.environ.update(environment)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(('127.0.0.1', port))
        listener.listen(16)
        # The socket stays owned by this process throughout startup; never probe
        # an unrelated service simply because a preselected port became occupied.
        print('LOCAL_PORT ' + str(listener.getsockname()[1]), flush=True)
        child_guards()
        import uvicorn
        config = uvicorn.Config('backend.api:app', host='127.0.0.1', port=listener.getsockname()[1],
            workers=1, reload=False, access_log=False, log_level='critical', log_config=None,
            proxy_headers=False, timeout_keep_alive=2, timeout_graceful_shutdown=3)
        uvicorn.Server(config).run(sockets=[listener])
        return 0
    except OSError:
        print('LOCAL_ERROR bind', flush=True)
        return 1
    except Exception:
        print('LOCAL_ERROR startup', flush=True)
        return 1
    finally:
        listener.close()


def request(port, method, path, timeout):
    # Direct literal loopback only: no proxies, redirects, cookies or credentials.
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        connection.request(method, path, headers={'Connection': 'close'})
        response = connection.getresponse()
        response.read(4096)
        return response.status
    finally:
        connection.close()


def stop(process):
    if process.poll() is None:
        try:
            if os.name == 'nt':
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    return process.poll() is not None


def verify(port=0, startup_timeout=20):
    process = None
    reader = None
    passed = 0
    failed = False
    try:
        # -I excludes user site/PYTHON* injection. Only this reviewed repository is
        # added to sys.path; application config imports happen in the clean child.
        bootstrap = "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('scripts.verify_localhost',run_name='__main__')"
        command = [sys.executable, '-I', '-c', bootstrap, str(ROOT), '--_child', '--port', str(port)]
        options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
        deadline = time.monotonic() + startup_timeout
        process = subprocess.Popen(command, cwd=ROOT, env=child_environment(), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, **options)
        messages = queue.Queue()
        def read_port():
            try:
                messages.put(process.stdout.readline())
            except (OSError, ValueError):
                messages.put('')
        reader = threading.Thread(target=read_port, daemon=True)
        reader.start()
        message = messages.get(timeout=max(0.01, deadline-time.monotonic())).strip()
        if message == 'LOCAL_ERROR bind':
            print('FAIL: selected loopback port is unavailable; unrelated processes were not touched.')
            failed = True
        else:
            match = re.fullmatch(r'LOCAL_PORT ([0-9]+)', message)
            if not match:
                raise RuntimeError('Temporary server did not start.')
            selected = int(match.group(1))
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Temporary server exited during startup.')
                try:
                    remaining = deadline-time.monotonic()
                    if request(selected, 'GET', '/api/health', max(0.01, min(2, remaining))) == 200:
                        break
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError('Temporary server startup timed out.')
            for method, path, expected in CHECKS:
                if process.poll() is not None:
                    raise RuntimeError('Temporary server exited.')
                actual = request(selected, method, path, 2)
                ok = actual == expected
                passed += int(ok)
                failed |= not ok
                print(f"{'PASS' if ok else 'FAIL'}: {method} {path}: {actual} (expected {expected})")
    except (Exception, KeyboardInterrupt):
        failed = True
        print('FAIL: localhost verification could not complete; diagnostics suppressed.')
    finally:
        if process is not None:
            try:
                cleaned = stop(process)
                failed |= not cleaned
                print(('PASS' if cleaned else 'FAIL') + ': temporary server stopped')
            except Exception:
                failed = True
                print('FAIL: temporary server cleanup did not complete')
            if reader is not None:
                reader.join(timeout=1)
            # Avoid an unbounded pipe-close wait if OS cleanup itself failed.
            if process.poll() is not None and (reader is None or not reader.is_alive()):
                if process.stdout is not None:
                    process.stdout.close()
    print(f"{'FAIL' if failed else 'PASS'}: offline localhost verification ({passed}/{len(CHECKS)} endpoint checks passed)")
    print('PENDING: live Supabase integration; no live service was tested.')
    return int(failed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0, help='0 selects a free loopback port; occupied ports fail safely.')
    parser.add_argument('--startup-timeout', type=float, default=20, help='Startup limit in seconds (1-60).')
    parser.add_argument('--_child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535 or not 1 <= args.startup_timeout <= 60:
        print('FAIL: invalid localhost port or startup timeout')
        return 1
    return serve(args.port) if args._child else verify(args.port, args.startup_timeout)


if __name__ == '__main__':
    raise SystemExit(main())
