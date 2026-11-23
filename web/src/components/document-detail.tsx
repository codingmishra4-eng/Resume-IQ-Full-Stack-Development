"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, FileText } from "lucide-react";
import type { StoredResume } from "@/lib/api";
import { date, count, safeMessage } from "@/lib/format";
import { useAuth } from "./providers";
import { Badge, Notice, PageHeading, Panel, Skeleton } from "./ui";
import { DeleteButton, DownloadButton } from "./documents";
export function DocumentDetail({ id }: { id: string }) {
  const { api } = useAuth();
  const [result, setResult] = useState<{
    document?: StoredResume;
    error?: string;
  }>({});
  useEffect(() => {
    const controller = new AbortController();
    void api
      .resume(id, controller.signal)
      .then((document) => {
        if (!controller.signal.aborted) setResult({ document });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setResult({ error: safeMessage(error) });
      });
    return () => controller.abort();
  }, [id, api]);
  const item = result.document;
  return (
    <>
      <Link className="back-link" href="/documents">
        <ArrowLeft size={16} /> Back to documents
      </Link>
      <PageHeading
        eyebrow="PRIVATE DOCUMENT"
        title={item?.metadata.file_name ?? "Document details"}
        description="Your stored original, with only safe metadata exposed."
      />
      {result.error ? (
        <Notice error>{result.error}</Notice>
      ) : !item ? (
        <Skeleton rows={4} />
      ) : (
        <Panel className="detail-panel">
          <div className="section-heading">
            <span className="file-icon large">
              <FileText size={30} />
            </span>
            <Badge tone="mint">Private</Badge>
          </div>
          <div className="metadata-grid">
            <div>
              <span>Type</span>
              <strong>{item.metadata.file_type.toUpperCase()}</strong>
            </div>
            <div>
              <span>Pages detected</span>
              <strong>{item.metadata.pages}</strong>
            </div>
            <div>
              <span>Word count</span>
              <strong>{count(item.metadata.word_count)}</strong>
            </div>
            <div>
              <span>Uploaded</span>
              <strong>{date(item.created_at)}</strong>
            </div>
          </div>
          <h3>Recognized sections</h3>
          <div className="chips">
            {item.metadata.section_order.length ? (
              item.metadata.section_order.map((name, index) => (
                <Badge key={index}>{name.replaceAll("_", " ")}</Badge>
              ))
            ) : (
              <span className="muted">No canonical sections detected.</span>
            )}
          </div>
          <div className="detail-actions">
            <DownloadButton resume={item} />
            <DeleteButton resume={item} />
            <Link className="text-link" href="/analyzer">
              Open resume workspace
            </Link>
          </div>
          <p className="muted text-sm">
            Download creates a short-lived link. Select “Save file” while it is
            available. After deletion, return to Documents to see your updated
            library.
          </p>
        </Panel>
      )}
    </>
  );
}
