import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/utils/api";
import { InputField } from "@/components/ui/InputField";
import { Button } from "@/components/ui/Button";

export function RegisterForm() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email, password, name || undefined);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="sf-authform" onSubmit={onSubmit}>
      <h1 className="sf-authform__title">{t("auth.register")}</h1>
      <InputField
        id="reg-name"
        label={t("auth.name")}
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoComplete="name"
      />
      <InputField
        id="reg-email"
        label={t("auth.email")}
        type="email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <InputField
        id="reg-password"
        label={t("auth.password")}
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={8}
      />
      {error && <p className="sf-authform__error">{error}</p>}
      <Button type="submit" disabled={busy}>
        {busy ? t("auth.pleaseWait") : t("auth.register")}
      </Button>
      <p className="sf-authform__alt">
        {t("auth.haveAccount")} <Link to="/login">{t("auth.login")}</Link>
      </p>
    </form>
  );
}
