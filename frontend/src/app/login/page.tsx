"use client";

import { FormEvent, useState } from "react";
import { KeyRound, LogIn, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLanguage } from "@/components/language-provider";
import { isSupabaseConfigured, supabase } from "@/lib/supabase";

export default function LoginPage() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);

    if (!supabase) {
      setMessage(t.supabaseMissing);
      setIsSubmitting(false);
      return;
    }

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: window.location.origin,
      },
    });
    setMessage(error ? error.message : t.magicLinkSent);
    setIsSubmitting(false);
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5 text-primary" aria-hidden="true" />
            {t.loginTitle}
          </CardTitle>
          <CardDescription>
            {isSupabaseConfigured ? t.loginConfiguredDesc : t.loginUnconfiguredDesc}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">
            <div className="flex items-center gap-2 font-medium">
              <ShieldAlert className="size-4" aria-hidden="true" />
              {t.loginLocalBoundaryTitle}
            </div>
            <p className="mt-1">{t.loginLocalBoundaryDescription}</p>
          </div>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <Label htmlFor="email">{t.emailLabel}</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={t.emailPlaceholder}
                required
              />
            </div>
            {message ? <p className="text-sm leading-6 text-muted-foreground">{message}</p> : null}
            <Button type="submit" disabled={isSubmitting}>
              <LogIn className="size-4" aria-hidden="true" />
              {t.sendMagicLink}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
