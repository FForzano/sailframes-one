import {
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  type SyntheticEvent,
} from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Bold, Italic, Link2, Underline } from "lucide-react";
import { clubsService, clubKeys } from "@/services/clubs";
import { groupsService, groupKeys } from "@/services/groups";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { InputField } from "@/components/ui/InputField";
import { userLabel } from "@/utils/format";
import { smartSearch } from "@/utils/smartSearch";
import type { PostOwnerType, UUID } from "@/types";
import styles from "./EntityFeed.module.css";

type MentionType = "user" | "club" | "group";
interface MentionCandidate {
  type: MentionType;
  id: UUID;
  label: string;
}

/** Match a `@query` still being typed right before the caret — used both to
 * open/filter the mention dropdown and, on selection, to know how much of
 * the text to replace. */
const MENTION_TRIGGER_RE = /@([^\s@]*)$/;

type FormatType = "bold" | "underline" | "italic";
const FORMAT_MARKERS: Record<FormatType, string> = { bold: "**", underline: "__", italic: "*" };

interface FormatSpan {
  type: FormatType;
  markerLen: number;
  innerStart: number;
  innerEnd: number;
}

/** Same precedence as `renderPostBody`'s parser (bold before italic, since
 * they share `*`) — finds every bold/underline/italic span in `text` so the
 * toolbar can tell whether the cursor/selection currently sits inside one. */
const FORMAT_RE = /\*\*([^*\n]+)\*\*|__([^_\n]+)__|\*([^*\n]+)\*/g;

function findFormatSpans(text: string): FormatSpan[] {
  const spans: FormatSpan[] = [];
  FORMAT_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = FORMAT_RE.exec(text))) {
    if (m[1] !== undefined) {
      spans.push({ type: "bold", markerLen: 2, innerStart: m.index + 2, innerEnd: m.index + 2 + m[1].length });
    } else if (m[2] !== undefined) {
      spans.push({ type: "underline", markerLen: 2, innerStart: m.index + 2, innerEnd: m.index + 2 + m[2].length });
    } else if (m[3] !== undefined) {
      spans.push({ type: "italic", markerLen: 1, innerStart: m.index + 1, innerEnd: m.index + 1 + m[3].length });
    }
  }
  return spans;
}

/** Bold/Italic/Underline/Link toolbar + textarea + @mention autocomplete for
 * a post body, shared between creating a post (`PostComposer`) and editing
 * an existing one — factored out so the two don't duplicate this logic. The
 * body itself is a controlled `value`/`onChange` pair; this component only
 * owns its own ephemeral UI state (mention dropdown, link dialog). */
export function PostBodyField({
  ownerType,
  ownerId,
  value,
  onChange,
  id,
  placeholder,
  autoFocus,
}: {
  ownerType: PostOwnerType;
  ownerId: UUID;
  value: string;
  onChange: (value: string) => void;
  id: string;
  placeholder: string;
  autoFocus?: boolean;
}) {
  const { t } = useTranslation();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // --- @mentions: candidates are the post's own club/group members (visible
  // to whoever can already post here) plus every club/group name, mirroring
  // the same "search over already-loaded lists" pattern as EntitySearch —
  // there's no dedicated backend search endpoint for this. ---
  const clubs = useQuery({ queryKey: clubKeys.all, queryFn: clubsService.list });
  const groups = useQuery({ queryKey: groupKeys.all, queryFn: () => groupsService.list() });
  const clubMembers = useQuery({
    queryKey: clubKeys.members(ownerId),
    queryFn: () => clubsService.members(ownerId),
    enabled: ownerType === "club",
  });
  const groupDetail = useQuery({
    queryKey: groupKeys.detail(ownerId),
    queryFn: () => groupsService.get(ownerId),
    enabled: ownerType === "group",
  });

  const mentionCandidates = useMemo((): MentionCandidate[] => {
    const members = ownerType === "club" ? clubMembers.data : groupDetail.data?.members;
    return [
      ...(members ?? [])
        .filter((m) => m.user)
        .map((m): MentionCandidate => ({ type: "user", id: m.user_id, label: userLabel(m.user) })),
      ...(clubs.data ?? []).map((c): MentionCandidate => ({ type: "club", id: c.id, label: c.name })),
      ...(groups.data ?? []).map((g): MentionCandidate => ({ type: "group", id: g.id, label: g.name })),
    ];
  }, [ownerType, clubMembers.data, groupDetail.data, clubs.data, groups.data]);

  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const [mentionActive, setMentionActive] = useState(0);
  const mentionResults =
    mentionQuery === null ? [] : smartSearch(mentionQuery, mentionCandidates, (c) => [c.label]).slice(0, 8);

  const closeMentions = () => {
    setMentionQuery(null);
    setMentionStart(null);
    setMentionActive(0);
  };

  const applyMention = (candidate: MentionCandidate) => {
    const el = textareaRef.current;
    if (!el || mentionStart === null) return;
    const caret = el.selectionStart;
    const token = `@[${candidate.label}](${candidate.type}:${candidate.id}) `;
    const next = value.slice(0, mentionStart) + token + value.slice(caret);
    onChange(next);
    closeMentions();
    requestAnimationFrame(() => {
      el.focus();
      const cursor = mentionStart + token.length;
      el.setSelectionRange(cursor, cursor);
    });
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value;
    onChange(next);
    setSelection({ start: e.target.selectionStart, end: e.target.selectionEnd });
    const caret = e.target.selectionStart;
    const match = MENTION_TRIGGER_RE.exec(next.slice(0, caret));
    if (match) {
      setMentionQuery(match[1]);
      setMentionStart(caret - match[1].length - 1);
      setMentionActive(0);
    } else {
      closeMentions();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionQuery === null || mentionResults.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setMentionActive((i) => (i + 1) % mentionResults.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setMentionActive((i) => (i - 1 + mentionResults.length) % mentionResults.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      applyMention(mentionResults[mentionActive]);
    } else if (e.key === "Escape") {
      closeMentions();
    }
  };

  // Tracks the textarea's current selection so the toolbar can show a marker
  // as "active" whenever the cursor sits inside (or the selection sits
  // inside) a span already using it, and so wrapSelection below can toggle
  // that whole span off instead of nesting a second copy.
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const trackSelection = (e: SyntheticEvent<HTMLTextAreaElement>) => {
    setSelection({ start: e.currentTarget.selectionStart, end: e.currentTarget.selectionEnd });
  };

  const formatSpans = useMemo(() => findFormatSpans(value), [value]);

  /** The span of `type` that fully contains the current selection (a
   * collapsed cursor counts as a zero-width selection "inside" the span),
   * if any — this is what makes a toolbar button light up, and what
   * wrapSelection removes when toggling a marker back off. */
  const activeSpan = (type: FormatType) =>
    formatSpans.find((s) => s.type === type && selection.start >= s.innerStart && selection.end <= s.innerEnd);

  /** Wraps the current selection (or a placeholder, if nothing is selected)
   * in the marker for `type` — used by the Bold/Italic/Underline toolbar
   * buttons. If the cursor/selection is already inside a span of that type,
   * strips its markers instead (so pressing the same button again toggles
   * the whole span off rather than nesting a second copy). Re-selects the
   * (un)wrapped text afterwards, translated by the marker length, so
   * clicking again keeps toggling the same spot. */
  const wrapSelection = (type: FormatType) => {
    const el = textareaRef.current;
    if (!el) return;
    const marker = FORMAT_MARKERS[type];
    const { selectionStart, selectionEnd } = el;
    const span = activeSpan(type);
    if (span) {
      const { markerLen } = span;
      const next =
        value.slice(0, span.innerStart - markerLen) +
        value.slice(span.innerStart, span.innerEnd) +
        value.slice(span.innerEnd + markerLen);
      onChange(next);
      requestAnimationFrame(() => {
        el.focus();
        const start = selectionStart - markerLen;
        const end = selectionEnd - markerLen;
        el.setSelectionRange(start, end);
        setSelection({ start, end });
      });
      return;
    }
    const selected = value.slice(selectionStart, selectionEnd) || t("gruppi.formatPlaceholder");
    const next = value.slice(0, selectionStart) + marker + selected + marker + value.slice(selectionEnd);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      const start = selectionStart + marker.length;
      const end = start + selected.length;
      el.setSelectionRange(start, end);
      setSelection({ start, end });
    });
  };

  const [linkModal, setLinkModal] = useState<{ selectionStart: number; selectionEnd: number } | null>(null);
  const [linkLabel, setLinkLabel] = useState("");
  const [linkUrl, setLinkUrl] = useState("");

  const openLinkModal = () => {
    const el = textareaRef.current;
    if (!el) return;
    const { selectionStart, selectionEnd } = el;
    setLinkLabel(value.slice(selectionStart, selectionEnd));
    setLinkUrl("");
    setLinkModal({ selectionStart, selectionEnd });
  };

  const confirmLink = (e: FormEvent) => {
    e.preventDefault();
    const el = textareaRef.current;
    if (!el || !linkModal || !linkUrl.trim()) return;
    const url = /^https?:\/\//i.test(linkUrl.trim()) ? linkUrl.trim() : `https://${linkUrl.trim()}`;
    const label = linkLabel.trim() || url;
    const { selectionStart, selectionEnd } = linkModal;
    const token = `[${label}](${url})`;
    const next = value.slice(0, selectionStart) + token + value.slice(selectionEnd);
    onChange(next);
    setLinkModal(null);
    requestAnimationFrame(() => {
      el.focus();
      const cursor = selectionStart + token.length;
      el.setSelectionRange(cursor, cursor);
    });
  };

  return (
    <>
      <div className={styles.formToolbar}>
        <Button
          type="button"
          variant="ghost"
          className={`sf-btn--icon-sm ${activeSpan("bold") ? "sf-btn--active" : ""}`}
          aria-label={t("gruppi.formatBold")}
          aria-pressed={!!activeSpan("bold")}
          onClick={() => wrapSelection("bold")}
        >
          <Bold size={15} />
        </Button>
        <Button
          type="button"
          variant="ghost"
          className={`sf-btn--icon-sm ${activeSpan("italic") ? "sf-btn--active" : ""}`}
          aria-label={t("gruppi.formatItalic")}
          aria-pressed={!!activeSpan("italic")}
          onClick={() => wrapSelection("italic")}
        >
          <Italic size={15} />
        </Button>
        <Button
          type="button"
          variant="ghost"
          className={`sf-btn--icon-sm ${activeSpan("underline") ? "sf-btn--active" : ""}`}
          aria-label={t("gruppi.formatUnderline")}
          aria-pressed={!!activeSpan("underline")}
          onClick={() => wrapSelection("underline")}
        >
          <Underline size={15} />
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="sf-btn--icon-sm"
          aria-label={t("gruppi.formatLink")}
          onClick={openLinkModal}
        >
          <Link2 size={15} />
        </Button>
      </div>
      <div className={styles.formField}>
        <textarea
          ref={textareaRef}
          className="sf-field__input"
          id={id}
          placeholder={placeholder}
          aria-label={placeholder}
          rows={3}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onSelect={trackSelection}
          onClick={trackSelection}
          onKeyUp={trackSelection}
          onBlur={() => setTimeout(closeMentions, 150)}
          autoFocus={autoFocus}
          required
        />
        {mentionQuery !== null && mentionResults.length > 0 && (
          <div className={styles.formMentions}>
            {mentionResults.map((c, i) => (
              <div
                key={`${c.type}-${c.id}`}
                className={`${styles.formMentionOption} ${i === mentionActive ? styles.formMentionOptionActive : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  applyMention(c);
                }}
              >
                <span>{c.label}</span>
                <span className={styles.formMentionType}>{t(`gruppi.mentionType.${c.type}`)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {linkModal && (
        <Modal title={t("gruppi.formatLink")} onClose={() => setLinkModal(null)}>
          <form onSubmit={confirmLink}>
            <InputField
              label={t("gruppi.linkLabelField")}
              id={`${id}-link-label`}
              value={linkLabel}
              onChange={(e) => setLinkLabel(e.target.value)}
              placeholder={t("gruppi.linkLabelPlaceholder")}
              autoFocus
            />
            <InputField
              label={t("gruppi.linkUrlField")}
              id={`${id}-link-url`}
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="https://…"
              required
            />
            <div className="sf-form__actions">
              <Button type="button" variant="ghost" onClick={() => setLinkModal(null)}>
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={!linkUrl.trim()}>
                {t("common.add")}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
