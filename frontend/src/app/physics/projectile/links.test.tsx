/** The two projectile pages link to each other from their headers (plan D9). */
import { render, screen, within } from "@testing-library/react";
import { vi } from "vitest";

import LinearPage from "./page";
import QuadraticPage from "./quadratic-drag/page";

// The labs themselves are tested on their own; only the headers matter here.
vi.mock("@/components/ProjectileLab", () => ({ ProjectileLab: () => null }));
vi.mock("@/components/QuadraticDragLab", () => ({ QuadraticDragLab: () => null }));

const header = () => within(screen.getByRole("banner"));

describe("the projectile pages", () => {
  it("links the linear-drag page to the quadratic-drag page", () => {
    render(<LinearPage />);
    expect(header().getByRole("link", { name: /quadratic drag/i })).toHaveAttribute(
      "href",
      "/physics/projectile/quadratic-drag",
    );
  });

  it("titles the quadratic-drag page and links back to the linear-drag page", () => {
    render(<QuadraticPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Projectile motion with quadratic drag" }),
    ).toBeInTheDocument();
    expect(header().getByRole("link", { name: /linear drag/i })).toHaveAttribute(
      "href",
      "/physics/projectile",
    );
  });
});
