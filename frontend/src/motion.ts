import type { PointerEvent } from "react";

const bounds = new WeakMap<Element, DOMRect>();
const reducedMotion = () =>
  typeof matchMedia === "function" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Pointer-follow 3D tilt and sheen for `.tilt` surfaces. Mouse only. */
export function tilt(strength = 8) {
  return {
    onPointerEnter(event: PointerEvent<HTMLElement>) {
      bounds.set(
        event.currentTarget,
        event.currentTarget.getBoundingClientRect(),
      );
    },
    onPointerMove(event: PointerEvent<HTMLElement>) {
      if (event.pointerType !== "mouse" || reducedMotion()) return;
      const target = event.currentTarget;
      const rect = bounds.get(target) ?? target.getBoundingClientRect();
      const x = Math.min(
        Math.max((event.clientX - rect.left) / rect.width, 0),
        1,
      );
      const y = Math.min(
        Math.max((event.clientY - rect.top) / rect.height, 0),
        1,
      );
      target.style.setProperty(
        "--rx",
        ((0.5 - y) * strength).toFixed(2) + "deg",
      );
      target.style.setProperty(
        "--ry",
        ((x - 0.5) * strength).toFixed(2) + "deg",
      );
      target.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
      target.style.setProperty("--my", (y * 100).toFixed(1) + "%");
    },
    onPointerLeave(event: PointerEvent<HTMLElement>) {
      bounds.delete(event.currentTarget);
      for (const name of ["--rx", "--ry", "--mx", "--my"])
        event.currentTarget.style.removeProperty(name);
    },
  };
}
