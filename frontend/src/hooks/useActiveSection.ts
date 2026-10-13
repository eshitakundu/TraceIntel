import { useEffect, useState } from "react";

/** Tracks which report section is in the reading band of the viewport. */
export function useActiveSection(ids: readonly string[], enabled: boolean) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    if (!enabled || typeof IntersectionObserver === "undefined") return;
    const visible = new Map<string, boolean>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries)
          visible.set(entry.target.id, entry.isIntersecting);
        const first = ids.find((id) => visible.get(id));
        if (first) setActive(first);
      },
      { rootMargin: "-20% 0px -65% 0px" },
    );
    for (const id of ids) {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    }
    return () => observer.disconnect();
  }, [ids, enabled]);
  return active;
}
