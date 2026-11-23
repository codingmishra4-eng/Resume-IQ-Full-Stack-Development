import type {
  Reporter,
  TestCase,
  TestResult,
  FullResult,
} from "@playwright/test/reporter";
// No errors, call arguments, browser output, attachments or credentials in reports.
export default class SafeReporter implements Reporter {
  private counts: Record<string, number> = {};
  onTestEnd(_test: TestCase, result: TestResult) {
    this.counts[result.status] = (this.counts[result.status] ?? 0) + 1;
  }
  onError() {
    process.stdout.write(
      "Browser harness error; sensitive details suppressed.\n",
    );
  }
  onEnd(result: FullResult) {
    process.stdout.write(
      `Browser results: ${JSON.stringify(this.counts)}; ${!this.counts.passed && this.counts.skipped ? "pending" : result.status}\n`,
    );
  }
}
