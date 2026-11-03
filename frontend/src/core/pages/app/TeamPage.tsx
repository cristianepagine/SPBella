import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type MemberWithPassword,
  type TeamMember,
  useAddMember,
  useChangeMember,
  useResetMemberPassword,
  useTeam,
} from "../../api/team";
import { useAuth } from "../../auth/AuthProvider";
import type { Role } from "../../auth/permissions";
import { Card, FormError, SubmitButton, TextField } from "../../components/form";

const ROLES: Role[] = ["reception", "professional", "owner"];

/** Equipe (só o dono): quem tem acesso, com qual perfil, e cadastro de pessoas novas. */
export function TeamPage() {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const team = useTeam(slug);
  const [password, setPassword] = useState<MemberWithPassword | null>(null);

  return (
    <div className="flex flex-col gap-4">
      {password && <TemporaryPassword data={password} onClose={() => setPassword(null)} />}
      <AddMember onAdded={setPassword} />
      <Card title={t("team.title")}>
        {team.isPending && <p role="status">{t("auth.loading")}</p>}
        {team.isError && <FormError error={team.error} />}
        {team.data && (
          <ul className="divide-y divide-slate-100">
            {team.data.map((member) => (
              <MemberRow key={member.id} member={member} onNewPassword={setPassword} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function AddMember({ onAdded }: { onAdded: (data: MemberWithPassword) => void }) {
  const { t } = useTranslation();
  const { slug } = useAuth();
  const add = useAddMember(slug);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("reception");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const created = await add.mutateAsync({ name, email, role }).catch(() => null);
    if (created) {
      onAdded(created);
      setName("");
      setEmail("");
    }
  }

  return (
    <Card title={t("team.addTitle")}>
      <form onSubmit={submit} noValidate>
        <FormError error={add.error} />
        <TextField label={t("team.name")} required value={name} onChange={(e) => setName(e.target.value)} />
        <TextField
          label={t("auth.email")}
          type="email"
          inputMode="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <RoleSelect label={t("team.role")} value={role} onChange={setRole} />
        <SubmitButton busy={add.isPending}>{t("team.add")}</SubmitButton>
      </form>
    </Card>
  );
}

function MemberRow({
  member,
  onNewPassword,
}: {
  member: TeamMember;
  onNewPassword: (data: MemberWithPassword) => void;
}) {
  const { t } = useTranslation();
  const { slug, state } = useAuth();
  const change = useChangeMember(slug);
  const reset = useResetMemberPassword(slug);
  const isMe = state.status === "authenticated" && state.user.id === member.id;

  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className={`font-medium ${member.is_active ? "" : "text-slate-400 line-through"}`}>
            {member.name} {isMe && <span className="text-sm text-slate-500">({t("team.you")})</span>}
          </p>
          <p className="truncate text-sm text-slate-500">{member.email}</p>
          {member.must_change_password && member.is_active && (
            <p className="text-sm text-amber-700">{t("team.pendingFirstLogin")}</p>
          )}
        </div>
        <span className="shrink-0 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-900">
          {member.is_active ? t(`roles.${member.role}`) : t("team.inactive")}
        </span>
      </div>

      {!isMe && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <RoleSelect
            label={t("team.changeRole", { name: member.name })}
            compact
            value={member.role}
            onChange={(role) => change.mutate({ id: member.id, role })}
          />
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            onClick={() => change.mutate({ id: member.id, is_active: !member.is_active })}
          >
            {member.is_active ? t("team.deactivate") : t("team.activate")}
          </button>
          {member.is_active && (
            <button
              type="button"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              onClick={() => reset.mutateAsync(member.id).then(onNewPassword, () => null)}
            >
              {t("team.newPassword")}
            </button>
          )}
        </div>
      )}
      <FormError error={change.error ?? reset.error} />
    </li>
  );
}

function RoleSelect({
  label,
  value,
  onChange,
  compact = false,
}: {
  label: string;
  value: Role;
  onChange: (role: Role) => void;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <label className={compact ? "text-sm" : "mb-4 block"}>
      <span className={compact ? "sr-only" : "mb-1 block font-medium text-slate-800"}>{label}</span>
      <select
        className={`rounded-xl border border-slate-300 bg-white ${compact ? "px-2 py-2 text-sm" : "w-full px-4 py-3"}`}
        value={value}
        onChange={(e) => onChange(e.target.value as Role)}
      >
        {ROLES.map((role) => (
          <option key={role} value={role}>
            {t(`roles.${role}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

function TemporaryPassword({ data, onClose }: { data: MemberWithPassword; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <section role="status" className="rounded-2xl border-2 border-emerald-600 bg-emerald-50 p-5">
      <p className="font-medium">{t("team.passwordFor", { name: data.member.name })}</p>
      <p className="my-3 select-all rounded-lg bg-white px-4 py-3 text-center font-mono text-xl tracking-wider">
        {data.temporary_password}
      </p>
      <p className="text-sm text-slate-700">{t("team.passwordHint", { email: data.member.email })}</p>
      <button type="button" onClick={onClose} className="mt-3 font-medium text-emerald-800 underline">
        {t("team.passwordDone")}
      </button>
    </section>
  );
}
