import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/utils/api";
import { InputField } from "@/components/ui/InputField";
import { Button } from "@/components/ui/Button";

export function LoginForm() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      const redirect = params.get("redirect");
      navigate(redirect ? decodeURIComponent(redirect) : "/app", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="sf-authform" onSubmit={onSubmit}>
      <h1 className="sf-authform__title">{t("auth.login")}</h1>
      <InputField
        id="login-email"
        label={t("auth.email")}
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <InputField
        id="login-password"
        label={t("auth.password")}
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {error && <p className="sf-authform__error">{error}</p>}
      <Button type="submit" disabled={busy}>
        {busy ? t("auth.pleaseWait") : t("auth.login")}
      </Button>
      <p className="sf-authform__alt">
        {t("auth.noAccount")} <Link to="/register">{t("auth.register")}</Link>
      </p>
    </form>
  );
}
