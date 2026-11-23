import { notFound } from "next/navigation";
import { z } from "zod";
import { DocumentDetail } from "@/components/document-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) notFound();
  return <DocumentDetail id={id} />;
}
