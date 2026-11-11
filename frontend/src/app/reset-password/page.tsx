"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Dna, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { resetPassword, ApiError } from "@/lib/api";

function ResetPasswordContent() {
  const token = useSearchParams().get("token");

  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(token ? null : "This reset link is missing its token.");
  const [doneMessage, setDoneMessage] = React.useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await resetPassword({ token, new_password: password });
      setDoneMessage(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset password. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center gap-1">
          <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Dna className="size-5" />
          </div>
          <CardTitle className="text-xl">Set a new password</CardTitle>
          <CardDescription>Choose a new password for your GeoLLM account</CardDescription>
        </CardHeader>

        <CardContent>
          {doneMessage ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 rounded-md border border-green-500/40 bg-green-500/10 px-3 py-2 text-sm text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-4 shrink-0" />
                {doneMessage}
              </div>
              <Button asChild className="w-full">
                <Link href="/login">Go to sign in</Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="password">New password</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirm">Confirm password</Label>
                <Input
                  id="confirm"
                  type="password"
                  required
                  minLength={8}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <AlertCircle className="size-4 shrink-0" />
                  {error}
                </div>
              )}

              <Button type="submit" className="w-full" disabled={loading || !token}>
                {loading && <Loader2 className="size-4 animate-spin" />}
                Update password
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                <Link href="/forgot-password" className="text-primary underline underline-offset-2">
                  Request a new link
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <React.Suspense fallback={null}>
      <ResetPasswordContent />
    </React.Suspense>
  );
}