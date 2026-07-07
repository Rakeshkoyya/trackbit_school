"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Send, StickyNote } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { eventTimeLabel } from "@/lib/format";

export function TaskAttachments({ taskId }: { taskId: string }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [note, setNote] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["attachments", taskId],
    queryFn: () => appApi.attachments(taskId),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["attachments", taskId] });
    qc.invalidateQueries({ queryKey: ["task", taskId] }); // history reflects it too
  };

  const addNote = useMutation({
    mutationFn: () => appApi.addNote(taskId, note.trim()),
    onSuccess: () => {
      setNote("");
      refresh();
    },
    onError: (e) => showApiError(e, "Could not add note"),
  });

  const addPhoto = useMutation({
    mutationFn: (file: File) => appApi.addPhoto(taskId, file),
    onSuccess: refresh,
    onError: (e) => showApiError(e, "Could not upload photo"),
  });

  const notes = items.filter((a) => a.kind === "note");
  const photos = items.filter((a) => a.kind === "photo");

  return (
    <div className="mt-6">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Notes & photos
      </h2>

      {photos.length > 0 ? (
        <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {photos.map((p) => (
            <a
              key={p.id}
              href={p.file_url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative aspect-square overflow-hidden rounded-lg border border-border"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={p.file_url ?? ""}
                alt={`Photo by ${p.uploaded_by_name}`}
                className="h-full w-full object-cover transition-transform group-hover:scale-105"
              />
            </a>
          ))}
        </div>
      ) : null}

      {notes.length > 0 ? (
        <ul className="mb-3 space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
              <p className="whitespace-pre-wrap">{n.content}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {n.uploaded_by_name} · {eventTimeLabel(n.created_at)}
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      {items.length === 0 ? (
        <p className="mb-3 flex items-center gap-1.5 text-sm text-muted-foreground">
          <StickyNote className="h-4 w-4" /> Add a note or a photo of proof.
        </p>
      ) : null}

      <div className="flex items-center gap-2">
        <Input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add a note…"
          onKeyDown={(e) => {
            if (e.key === "Enter" && note.trim()) addNote.mutate();
          }}
        />
        <Button
          size="icon"
          variant="outline"
          aria-label="Add note"
          disabled={!note.trim() || addNote.isPending}
          onClick={() => addNote.mutate()}
        >
          <Send className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="outline"
          aria-label="Add photo"
          disabled={addPhoto.isPending}
          onClick={() => fileRef.current?.click()}
        >
          <ImagePlus className="h-4 w-4" />
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) addPhoto.mutate(f);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
