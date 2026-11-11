"use client";

import * as React from "react";
import Link from "next/link";
import { Dna, AlertCircle, Loader2, MailCheck, Eye, EyeOff } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { register, resendVerification, ApiError } from "@/lib/api";
import type { UserRole } from "@/lib/types";

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: "researcher", label: "Researcher" },
  { value: "clinician", label: "Clinician" },
  { value: "student", label: "Student" },
  { value: "admin", label: "Admin" },
];

export default function RegisterPage() {
  const [sentTo, setSentTo] = React.useState<string | null>(null);
  const [resendMessage, setResendMessage] = React.useState<string | null>(null);
  const [showPassword, setShowPassword] = React.useState(false);
  const [fullName, setFullName] = React.useState("");
  const [username, setUsername] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [role, setRole] = React.useState<UserRole>("researcher");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({
        full_name: fullName,
        username,
        email,
        password,
        role,
      });
      setSentTo(email);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }
  async function handleResend() {
    if (!sentTo) return;
    try {
      const res = await resendVerification(sentTo);
      setResendMessage(res.message);
    } catch {
      setResendMessage("Could not send the email. Please try again.");
    }
  }

  if (sentTo) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-sm">
          <CardHeader className="items-center text-center gap-1">
            <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <MailCheck className="size-5" />
            </div>
            <CardTitle className="text-xl">Check your email</CardTitle>
            <CardDescription>
              We sent a verification link to <span className="font-medium text-foreground">{sentTo}</span>.
              Click it to activate your account.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button type="button" variant="outline" className="w-full" onClick={handleResend}>
              Resend email
            </Button>
            {resendMessage && <p className="text-center text-sm text-muted-foreground">{resendMessage}</p>}
            <p className="text-center text-sm text-muted-foreground">
              <Link href="/login" className="text-primary underline underline-offset-2">Back to sign in</Link>
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center gap-1">
          <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Dna className="size-5" />
          </div>
          <CardTitle className="text-xl">Create an account</CardTitle>
          <CardDescription>Start searching GEO datasets with GeoBERT</CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="fullName">Name</Label>
              <Input
                id="fullName"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Jane Doe"
                autoComplete="name"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                required
                minLength={3}
                pattern="[a-zA-Z0-9_.\-]+"
                title="Letters, numbers, underscores, dots, and hyphens only"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="jane_doe"
                autoComplete="username"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>

              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  className="pr-10"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="role">User role</Label>
              <Select value={role} onValueChange={(v) => setRole(v as UserRole)}>
                <SelectTrigger id="role">
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <AlertCircle className="size-4 shrink-0" />
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="size-4 animate-spin" />}
              Create account
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-primary underline underline-offset-2">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
