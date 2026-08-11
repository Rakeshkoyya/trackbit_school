"use client";

/**
 * Settings → Student categories (`D-129`).
 *
 * The founder's framing: *"category is nothing but the type of student like
 * hosteller or dayscholer … lets make this as configuration so we can put this
 * editing under org settings and then it will reflect every where"*.
 *
 * This is the one place the vocabulary is edited. Everything else — the student
 * directory, a fee structure's category, a timetable block's roster — holds a
 * **reference** to a row here, so adding one makes it appear on all three
 * screens and renaming one changes the word everywhere without moving anybody.
 *
 * Two things this section is careful about:
 *
 *   · it shows **what depends on each category** before offering to remove it.
 *     Removal un-assigns every student on it, which is a fine thing to allow
 *     and a terrible thing to do by accident;
 *   · renaming is offered plainly, with no warning, because it is genuinely
 *     safe now. It was not before: a block that served hostellers found them by
 *     matching this very string, so a rename here used to empty every hostel
 *     roll in the school.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { StudentCategory } from "@/lib/school-types";

function usedBy(c: StudentCategory): string | null {
  const bits: string[] = [];
  if (c.student_count) {
    bits.push(`${c.student_count} student${c.student_count === 1 ? "" : "s"}`);
  }
  if (c.block_count) {
    bits.push(`${c.block_count} block${c.block_count === 1 ? "" : "s"}`);
  }
  return bits.length ? bits.join(" · ") : null;
}

export function StudentCategoriesSection() {
  const qc = useQueryClient();
  const [adding, setAdding] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const { data: categories = [], isLoading } = useQuery({
    queryKey: ["categories"], queryFn: schoolApi.categories,
  });

  const refresh = () => {
    // Every surface that renders a category reads this same key.
    qc.invalidateQueries({ queryKey: ["categories"] });
    qc.invalidateQueries({ queryKey: ["timetable-blocks"] });
    qc.invalidateQueries({ queryKey: ["students"] });
  };

  const add = useMutation({
    mutationFn: () => schoolApi.createCategory(adding.trim()),
    onSuccess: () => { refresh(); setAdding(""); toast.success("Category added"); },
    onError: (e) => showApiError(e, "Could not add the category"),
  });

  const rename = useMutation({
    mutationFn: (id: string) => schoolApi.renameCategory(id, draft.trim()),
    onSuccess: () => { refresh(); setEditingId(null); toast.success("Category renamed"); },
    onError: (e) => showApiError(e, "Could not rename it"),
  });

  const remove = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) =>
      schoolApi.deleteCategory(id, force),
    onSuccess: () => { refresh(); toast.success("Category removed"); },
    onError: (e) => showApiError(e, "Could not remove it"),
  });

  const seed = useMutation({
    mutationFn: schoolApi.seedCategories,
    onSuccess: () => { refresh(); toast.success("Added Day Scholar and Hosteller"); },
    onError: (e) => showApiError(e, "Could not add the defaults"),
  });

  const askRemove = (c: StudentCategory) => {
    const used = usedBy(c);
    const message = used
      ? `Remove “${c.name}”?\n\nIt is used by ${used}. They keep their records — `
        + "they simply stop being in this category, and any block restricted to "
        + "it reopens to the whole class."
      : `Remove “${c.name}”?`;
    if (window.confirm(message)) {
      remove.mutate({ id: c.id, force: Boolean(used) });
    }
  };

  return (
    <section className="mt-5 rounded-xl border border-border bg-card p-5">
      <h2 className="mb-1 text-sm font-semibold">Student categories</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        The type of student — hosteller, day scholar, and anything else your
        school separates on. Used by the student record, fee structures, and
        timetable blocks that run for one group only. Renaming one is safe:
        everything follows it.
      </p>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : categories.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-6 text-center">
          <p className="text-sm text-muted-foreground">
            No categories yet. Most schools start with two.
          </p>
          <Button size="sm" variant="outline" className="mt-3"
            disabled={seed.isPending} onClick={() => seed.mutate()}>
            Add Day Scholar and Hosteller
          </Button>
        </div>
      ) : (
        <ul className="mb-3 divide-y divide-border rounded-lg border border-border">
          {categories.map((c) => (
            <li key={c.id} className="flex items-center gap-2 px-3 py-2">
              {editingId === c.id ? (
                <>
                  <Input className="h-8 flex-1" value={draft} autoFocus
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && draft.trim()) rename.mutate(c.id);
                      if (e.key === "Escape") setEditingId(null);
                    }} />
                  <Button size="sm" variant="ghost" aria-label="Save name"
                    disabled={!draft.trim() || rename.isPending}
                    onClick={() => rename.mutate(c.id)}>
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="ghost" aria-label="Cancel"
                    onClick={() => setEditingId(null)}>
                    <X className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm font-medium">{c.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {/* Zero is a real answer — "not used yet", not missing data. */}
                    {usedBy(c) ?? "not used yet"}
                  </span>
                  <Button size="sm" variant="ghost" aria-label={`Rename ${c.name}`}
                    onClick={() => { setEditingId(c.id); setDraft(c.name); }}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" aria-label={`Remove ${c.name}`}
                    disabled={remove.isPending} onClick={() => askRemove(c)}>
                    <X className="h-4 w-4 text-muted-foreground hover:text-rose-500" />
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <form className="flex gap-2"
        onSubmit={(e) => { e.preventDefault(); if (adding.trim()) add.mutate(); }}>
        <Input className="h-9 max-w-xs" placeholder="Add a category — e.g. Transport"
          value={adding} onChange={(e) => setAdding(e.target.value)} />
        <Button type="submit" size="sm" variant="outline"
          disabled={!adding.trim() || add.isPending}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </form>
    </section>
  );
}
