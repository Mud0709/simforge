import { render, screen, within } from "@testing-library/react";

import { Workspace } from "./Workspace";

const PLACEHOLDERS = {
  visualisation: "Charts appear here.",
  results: "Numbers appear here.",
  assumptions: "Assumptions appear here.",
  validation: "Checks appear here.",
};
const region = (name: string) => within(screen.getByRole("region", { name }));

describe("Workspace", () => {
  it("shows each region's placeholder until it has content", () => {
    render(
      <Workspace
        parameters={<p>form</p>}
        visualisation={null}
        results={<p>42</p>}
        assumptions={null}
        validation={null}
        placeholders={PLACEHOLDERS}
      />,
    );
    expect(region("Visualisation").getByText("Charts appear here.")).toBeInTheDocument();
    expect(region("Results").getByText("42")).toBeInTheDocument();
    expect(region("Results").queryByText("Numbers appear here.")).not.toBeInTheDocument();
  });

  it("marks every input-dependent region when the results are out of date", () => {
    render(
      <Workspace
        parameters={<p>form</p>}
        visualisation={<p>chart</p>}
        results={<p>42</p>}
        assumptions={<p>assumed</p>}
        validation={<p>checked</p>}
        placeholders={PLACEHOLDERS}
        staleNote="Inputs changed."
      />,
    );
    for (const name of ["Visualisation", "Results", "Validation"]) {
      expect(region(name).getByText("Inputs changed.")).toBeInTheDocument();
    }
    // Nothing to mark while a region still shows its placeholder.
  });

  it("does not mark placeholders as out of date", () => {
    render(
      <Workspace
        parameters={<p>form</p>}
        visualisation={null}
        results={null}
        assumptions={null}
        validation={null}
        placeholders={PLACEHOLDERS}
        staleNote="Inputs changed."
      />,
    );
    expect(screen.queryByText("Inputs changed.")).not.toBeInTheDocument();
  });

  it("announces only a short status line, not the whole results area", () => {
    const { container } = render(
      <Workspace
        parameters={<p>form</p>}
        visualisation={<p>chart</p>}
        results={<p>42</p>}
        assumptions={null}
        validation={null}
        placeholders={PLACEHOLDERS}
        status="Run complete."
      />,
    );
    const live = container.querySelectorAll("[aria-live]");
    expect(live).toHaveLength(1);
    expect(live[0]).toHaveTextContent(/^Run complete\.$/);
  });
});
