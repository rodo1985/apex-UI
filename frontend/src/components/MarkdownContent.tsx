import type { ReactNode } from "react";

type MarkdownBlock =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] };

/**
 * Render a lightweight markdown document for profile sections.
 *
 * Parameters:
 *   markdown: Raw markdown string stored in the portal backend.
 *
 * Returns:
 *   JSX.Element: Readable headings, paragraphs, and lists.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function MarkdownContent({ markdown }: { markdown: string }) {
  const blocks = parseMarkdown(markdown);

  if (blocks.length === 0) {
    return <p className="markdown-empty">No details available yet.</p>;
  }

  return (
    <div className="markdown-content">
      {blocks.map((block, index) => renderBlock(block, index))}
    </div>
  );
}

/**
 * Parse a compact subset of markdown into renderable blocks.
 *
 * Parameters:
 *   markdown: Raw markdown string from the backend.
 *
 * Returns:
 *   MarkdownBlock[]: Structured headings, paragraphs, and lists.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function parseMarkdown(markdown: string): MarkdownBlock[] {
  const lines = markdown.split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let paragraphLines: string[] = [];
  let listItems: string[] = [];

  /**
   * Flush the current paragraph lines into a single block.
   *
   * Parameters:
   *   None.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function flushParagraph() {
    if (paragraphLines.length === 0) {
      return;
    }

    blocks.push({
      type: "paragraph",
      text: stripInlineMarkdown(paragraphLines.join(" ")),
    });
    paragraphLines = [];
  }

  /**
   * Flush the current list items into one list block.
   *
   * Parameters:
   *   None.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function flushList() {
    if (listItems.length === 0) {
      return;
    }

    blocks.push({
      type: "list",
      items: listItems.map((item) => stripInlineMarkdown(item)),
    });
    listItems = [];
  }

  for (const line of lines) {
    const trimmedLine = line.trim();

    if (!trimmedLine) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = /^(#{1,3})\s+(.*)$/.exec(trimmedLine);
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: headingMatch[1].length as 1 | 2 | 3,
        text: stripInlineMarkdown(headingMatch[2]),
      });
      continue;
    }

    const listMatch = /^[-*]\s+(.*)$/.exec(trimmedLine);
    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch[1]);
      continue;
    }

    flushList();
    paragraphLines.push(trimmedLine);
  }

  flushParagraph();
  flushList();
  return blocks;
}

/**
 * Remove inline markdown markers that the simple renderer does not style.
 *
 * Parameters:
 *   text: Raw markdown line content.
 *
 * Returns:
 *   string: Plain text suitable for rendering.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function stripInlineMarkdown(text: string): string {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .trim();
}

/**
 * Render one parsed markdown block.
 *
 * Parameters:
 *   block: Parsed markdown block.
 *   index: Stable array index used as the React key.
 *
 * Returns:
 *   ReactNode: JSX for the given block type.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function renderBlock(block: MarkdownBlock, index: number): ReactNode {
  if (block.type === "heading") {
    if (block.level === 1) {
      return <h3 key={index}>{block.text}</h3>;
    }

    if (block.level === 2) {
      return <h4 key={index}>{block.text}</h4>;
    }

    return <h5 key={index}>{block.text}</h5>;
  }

  if (block.type === "list") {
    return (
      <ul key={index}>
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{item}</li>
        ))}
      </ul>
    );
  }

  return <p key={index}>{block.text}</p>;
}
