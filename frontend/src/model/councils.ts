/** Council dashboard links on the Relief card (#94). */
import { listAttr, safeUrl, stringAttr } from "../ha/format";

export interface CouncilLink {
  name: string;
  /** Safe http(s) URL, or undefined when the upstream value is not one (shown without a link). */
  url?: string;
}

function toLink(value: unknown): CouncilLink | undefined {
  if (!value || typeof value !== "object") return undefined;
  const item = value as { name?: unknown; url?: unknown };
  const url = safeUrl(item.url);
  const name = stringAttr(item.name) ?? stringAttr(item.url);
  return name ? { name, url } : undefined;
}

function sameUrl(a: string | undefined, b: string | undefined): boolean {
  const norm = (u?: string) => u?.replace(/^https?:\/\//i, "").replace(/\/+$/, "").toLowerCase();
  return !!a && !!b && norm(a) === norm(b);
}

/**
 * The entry's own council dashboard (`council` attribute) and, only when asked, the
 * neighbouring ones (`nearby_councils`), without repeating the own one.
 */
export function councilLinks(
  own: unknown,
  nearby: unknown,
  showNearby: boolean,
): { own?: CouncilLink; nearby: CouncilLink[] } {
  const ownLink = toLink(own);
  const nearbyLinks = showNearby
    ? listAttr(nearby)
        .map(toLink)
        .filter((c): c is CouncilLink => !!c && !(ownLink && sameUrl(c.url, ownLink.url)))
    : [];
  return { own: ownLink, nearby: nearbyLinks };
}
