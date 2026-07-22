/** Structured legal-document content, rendered by LegalDocument.tsx. Kept as
 * data (not JSX) so the same renderer handles both documents in both
 * languages, and so the text stays easy to diff when a clause changes. */
export interface LegalBlock {
  /** A paragraph, or a bulleted list of points. */
  type: "p" | "ul";
  /** For type "p". */
  text?: string;
  /** For type "ul". */
  items?: string[];
}

export interface LegalSection {
  /** Section heading, e.g. "1. Provider of the service". */
  title: string;
  blocks: LegalBlock[];
}

export interface LegalDoc {
  /** Document title shown as the page heading. */
  title: string;
  /** Short lead paragraph shown under the title, before the sections. */
  lead?: string;
  sections: LegalSection[];
}

/** Both language variants of one document. */
export type LegalDocByLang = Record<"it" | "en", LegalDoc>;
