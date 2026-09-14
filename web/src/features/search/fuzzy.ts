/**
 * The command palette's fuzzy matcher.
 *
 * Case-insensitive SUBSEQUENCE matching with a scoring model tuned for a
 * small, expert-facing command set (the spec's contract):
 *   +3  per consecutive matched character (runs beat scattered hits)
 *   +5  per word-start match (index 0, after a separator, or a camelCase
 *       boundary — "netw" should rank `Networks` over `Connectivity`)
 *   -1  per gap (an unmatched character of the text between matched
 *       characters — spread matches rank below tight ones)
 *   null when the query is not a subsequence of the text at all
 *   0 for the empty query (everything ties; registry order wins)
 *
 * Pure function — no state, no dependencies; trivially unit-testable.
 */

/** Is `text[index]` the first character of a word? */
function isWordStart(text: string, index: number): boolean {
  if (index === 0) return true;
  const previous = text[index - 1];
  const current = text[index];
  // after a separator (covers "contract detail", "api-explorer", snake_case)
  if (previous === " " || previous === "-" || previous === "_" || previous === "/") {
    return true;
  }
  // camelCase boundary: a lowercase letter followed by an uppercase letter
  const previousIsLowerLetter =
    previous === previous.toLowerCase() && previous !== previous.toUpperCase();
  const currentIsUpperLetter =
    current === current.toUpperCase() && current !== current.toLowerCase();
  return previousIsLowerLetter && currentIsUpperLetter;
}

/**
 * Score how well `text` matches `query` (higher is better).
 * Returns null when the query characters are not a subsequence of text.
 */
export function fuzzyMatch(query: string, text: string): number | null {
  if (query.length === 0) return 0;

  const needle = query.toLowerCase();
  const haystack = text.toLowerCase();

  let score = 0;
  let needleIndex = 0;
  let lastMatchIndex = -1;

  for (let index = 0; index < haystack.length && needleIndex < needle.length; index += 1) {
    if (haystack[index] === needle[needleIndex]) {
      if (lastMatchIndex !== -1 && index === lastMatchIndex + 1) {
        score += 3; // consecutive character
      } else if (isWordStart(text, index)) {
        score += 5; // word-start character
      }
      lastMatchIndex = index;
      needleIndex += 1;
    } else if (lastMatchIndex !== -1) {
      score -= 1; // a gap between matched characters
    }
  }

  if (needleIndex < needle.length) return null; // query not exhausted → no match
  return score;
}
