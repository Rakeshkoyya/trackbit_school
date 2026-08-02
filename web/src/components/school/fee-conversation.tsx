"use client";

/**
 * The fee conversation history (V1-10, `D-84`) — append-only, per student.
 *
 * The founder's requirement in his own words: *"I know — conversation history.
 * I want you to maintain this in the fee management system for every student."*
 *
 * `S-161` is what makes it worth the table: **"reminded" is an event; "spoke to
 * the mother — paying after the 15th" is what makes the row go away.** Without
 * it the same family is rung every week by a different person, each opening with
 * the same question — and the school looks disorganised to exactly the people it
 * is asking for money.
 *
 * Nothing here is ever edited: a correction is another row (law 3).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessagesSquare } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

const KINDS = [
  ["call", "Called them"],
  ["visit", "They came in"],
  ["message", "Messaged"],
  ["note", "Note"],
] as const;

export function FeeConversation({ studentFeeId }: { studentFeeId: string }) {
  const qc = useQueryClient();
  const [kind, setKind] = useState<string>("call");
  const [said, setSaid] = useState("");
  const [promised, setPromised] = useState("");

  const { data: notes = [] } = useQuery({
    queryKey: ["fee-notes", studentFeeId],
    queryFn: () => schoolApi.feeNotes(studentFeeId),
  });
  const add = useMutation({
    mutationFn: () => schoolApi.addFeeNote(studentFeeId, {
      kind, said: said.trim(), promised_date: promised || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fee-notes", studentFeeId] });
      qc.invalidateQueries({ queryKey: ["collection"] });
      setSaid(""); setPromised("");
      toast.success("Recorded");
    },
    onError: (e) => showApiError(e, "Could not record it"),
  });

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <MessagesSquare className="h-4 w-4" /> Conversation history
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        What the family said, so the next person to ring is not the fourth this month
        to ask the same question.
      </p>

      <div className="mt-3 space-y-2">
        <div className="flex flex-wrap gap-1.5">
          {KINDS.map(([value, label]) => (
            <button key={value} type="button" onClick={() => setKind(value)}
              className={`rounded-md border px-2.5 py-1 text-xs transition ${
                kind === value ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:bg-muted/40"}`}>
              {label}
            </button>
          ))}
        </div>
        <div>
          <Label htmlFor="said">What did they say?</Label>
          <Input id="said" value={said} onChange={(e) => setSaid(e.target.value)}
            placeholder="spoke to the mother — paying after the 15th" />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <Label htmlFor="promised">They promised (optional)</Label>
            <Input id="promised" type="date" value={promised}
              onChange={(e) => setPromised(e.target.value)} />
          </div>
          <Button disabled={!said.trim() || add.isPending} onClick={() => add.mutate()}>
            Record it
          </Button>
        </div>
      </div>

      {notes.length ? (
        <ul className="mt-4 space-y-2 border-t border-border pt-3">
          {notes.map((n) => (
            <li key={n.id} className="text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{n.kind}</Badge>
                <span className="text-xs text-muted-foreground">
                  {String(n.created_at).slice(0, 10)}
                  {n.author_name ? ` · ${n.author_name}` : ""}
                  {n.promised_date ? ` · promised ${n.promised_date}` : ""}
                </span>
              </div>
              {n.said ? <p className="mt-0.5">{n.said}</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">
          Nothing recorded yet.
        </p>
      )}
    </section>
  );
}
