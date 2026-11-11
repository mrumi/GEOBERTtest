"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Dna, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { verifyEmail, ApiError } from "@/lib/api";

function VerifyEmailContent() {
  const token = useSearchParams().get("token");
  const [status, setStatus] = React.useState<"loading" | "success" | "error">(token ? "loading" : "error");
  const [message, setMessage] = React.useState(token ? "" : "This verification link is missing its token.");
  // Guards React strict-mode's double effect run — the token is single-use,
  // so a second call would fail and overwrite the success message.
  const called = React.useRef(false);

  React.useEffect(() => {
    if (!token || called.current) return;
    called.current = true;
    verifyEmail(token)
      .then((res) => {
        setStatus("success");
        setMessage(res.message);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : "Verification failed. Please try again.");
      });
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center gap-1">
          <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Dna className="size-5" />
          </div>
          <CardTitle className="text-xl">Email verification</CardTitle>
          <CardDescription>
            {status === "loading" ? "Verifying your email…" : "GeoLLM account"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status === "loading" && (
            <div className="flex justify-center">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {status === "success" && (
            <div className="flex items-center gap-2 rounded-md border border-green-500/40 bg-green-500/10 px-3 py-2 text-sm text-green-600 dark:text-green-400">
              <CheckCircle2 className="size-4 shrink-0" />
              {message}
            </div>
          )}
          {status === "error" && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="size-4 shrink-0" />
              {message}
            </div>
          )}
          {status !== "loading" && (
            <Button asChild className="w-full">
              <Link href="/login">Go to sign in</Link>
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function VerifyEmailPage() {
  // useSearchParams needs a Suspense boundary for Next.js production builds.
  return (
    <React.Suspense fallback={null}>
      <VerifyEmailContent />
    </React.Suspense>
  );
}