"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowRight, Copy, PartyPopper, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";

function Stepper({ step }: { step: number }) {
  return (
    <div className="mb-8 flex items-center justify-center gap-2">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`h-1.5 rounded-full transition-all ${
            i === step ? "w-8 bg-primary" : i < step ? "w-4 bg-success" : "w-4 bg-muted"
          }`}
        />
      ))}
    </div>
  );
}

function AddMembersStep({ onNext }: { onNext: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [added, setAdded] = useState<{ name: string; link: string }[]>([]);

  const invite = useMutation({
    mutationFn: () =>
      appApi.inviteMember({ name: name.trim(), email: contact.trim(), role: "teacher" }),
    onSuccess: (res) => {
      setAdded((a) => [...a, { name: res.name, link: res.invite_url }]);
      setName("");
      setContact("");
      qc.invalidateQueries({ queryKey: ["members"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not add"),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Add your team</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Each person gets a link — paste it into your WhatsApp or SMS. No passwords.
      </p>

      <form
        className="mt-6 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim() && contact.trim()) invite.mutate();
        }}
      >
        <div className="flex gap-2">
          <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            placeholder="Phone or email"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
          />
          <Button type="submit" disabled={invite.isPending || !name.trim() || !contact.trim()}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </form>

      {added.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {added.map((a, i) => (
            <li key={i} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
              <Avatar name={a.name} />
              <span className="flex-1 truncate">{a.name}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(a.link);
                  toast.success("Link copied");
                }}
                className="inline-flex items-center gap-1 text-xs text-primary"
              >
                <Copy className="h-3 w-3" /> Copy link
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-8 flex items-center justify-between">
        <button onClick={onNext} className="text-sm text-muted-foreground hover:text-foreground">
          Skip for now
        </button>
        <Button onClick={onNext}>
          Next <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function FirstTaskStep({ onNext }: { onNext: () => void }) {
  const [title, setTitle] = useState("");
  const boards = useQuery({ queryKey: ["boards"], queryFn: appApi.boards });
  const members = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const [assignee, setAssignee] = useState("");

  const firstBoard =
    boards.data ? [...boards.data.my_boards, ...boards.data.other_public][0] : undefined;

  const create = useMutation({
    mutationFn: () =>
      appApi.createTask({
        board_id: firstBoard!.id,
        title: title.trim(),
        assignee_id: assignee || null,
      }),
    onSuccess: () => {
      toast.success("First task created 🎉");
      onNext();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not create"),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Create your first task</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Add it to your <strong>{firstBoard?.name ?? "General"}</strong> board and assign it to someone.
      </p>

      <form
        className="mt-6 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim() && firstBoard) create.mutate();
        }}
      >
        <div>
          <Label htmlFor="o-title">What needs doing?</Label>
          <Input id="o-title" autoFocus value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="o-assignee">Assign to</Label>
          <select
            id="o-assignee"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm"
          >
            <option value="">Leave unassigned (anyone claims)</option>
            {members.data?.members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between pt-4">
          <button
            type="button"
            onClick={onNext}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Skip
          </button>
          <Button type="submit" disabled={create.isPending || !title.trim()}>
            {create.isPending ? "Creating…" : "Create & finish"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function DoneStep() {
  const router = useRouter();
  return (
    <div className="text-center">
      <div className="tb-pop-in mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#e7efe9]">
        <PartyPopper className="h-8 w-8 text-success" />
      </div>
      <h1 className="mt-5 text-2xl font-semibold tracking-tight">You&apos;re all set</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Your team and tasks live on your Home screen. That&apos;s where the day starts.
      </p>
      <Button size="lg" className="mt-8" onClick={() => router.replace("/tasks")}>
        Get started <ArrowRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

function OnboardingInner() {
  const [step, setStep] = useState(0);
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 py-10">
      <Stepper step={step} />
      <div className="rounded-xl border border-border bg-card p-6">
        {step === 0 ? <AddMembersStep onNext={() => setStep(1)} /> : null}
        {step === 1 ? <FirstTaskStep onNext={() => setStep(2)} /> : null}
        {step === 2 ? <DoneStep /> : null}
      </div>
      {step < 2 ? (
        <button
          onClick={() => (window.location.href = "/tasks")}
          className="mt-4 text-center text-xs text-muted-foreground hover:text-foreground"
        >
          Skip setup
        </button>
      ) : null}
    </main>
  );
}

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <OnboardingInner />
    </AuthGuard>
  );
}
