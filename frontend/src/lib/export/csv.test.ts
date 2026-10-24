import { csvFilename, toCsv, type Table } from "./csv";

// Every expected string below is written out by hand from the format rules (RFC 4180, units
// in square brackets, shortest round-trip numbers, `'` before risky text), never produced
// by the code under test.

const table = (columns: Table["columns"]): Table => ({ name: "t", label: "t", columns });

describe("toCsv", () => {
  it("writes headers with units, CRLF line endings and RFC 4180 quoting", () => {
    const csv = toCsv(
      table([
        { name: "t", unit: "s", values: [0, 0.5] },
        { name: "label", values: ["a,b", 'say "hi"'] },
        { name: "text", values: ["two\nlines", "plain"] },
      ]),
    );
    expect(csv).toBe('t [s],label,text\r\n0,"a,b","two\nlines"\r\n0.5,"say ""hi""",plain\r\n');
  });

  it("quotes a header whose unit contains a comma", () => {
    const csv = toCsv(table([{ name: "k", unit: "model units, per worker", values: [1] }]));
    expect(csv).toBe('"k [model units, per worker]"\r\n1\r\n');
  });

  it("quotes a field containing a carriage return", () => {
    expect(toCsv(table([{ name: "a", values: ["x\ry"] }]))).toBe('a\r\n"x\ry"\r\n');
  });

  it("writes numbers as the shortest string that round-trips", () => {
    expect(toCsv(table([{ name: "x", values: [0.1 + 0.2] }]))).toBe("x\r\n0.30000000000000004\r\n");
  });

  it.each([
    ["1e-300", 1e-300],
    ["-0", -0],
    ["5e-324", 5e-324],
    ["1/3", 1 / 3],
    ["0.1 + 0.2", 0.1 + 0.2],
    ["the largest double", Number.MAX_VALUE],
    ["2^53 + 2", 2 ** 53 + 2],
  ])("round-trips %s exactly through Number(cell)", (_label, x) => {
    const cell = toCsv(table([{ name: "x", values: [x] }])).split("\r\n")[1]!;
    expect(Object.is(Number(cell), x)).toBe(true);
  });

  it("writes -0 as -0 (String(-0) would lose the sign)", () => {
    expect(toCsv(table([{ name: "x", values: [-0] }]))).toBe("x\r\n-0\r\n");
  });

  it("writes null, undefined and the end of a shorter column as empty cells", () => {
    const csv = toCsv(
      table([
        { name: "a", values: [1, 2, 3] },
        { name: "b", values: [null, 5] },
        { name: "c", values: [undefined, 7, null] },
      ]),
    );
    expect(csv).toBe("a,b,c\r\n1,,\r\n2,5,7\r\n3,,\r\n");
  });

  it("writes booleans as true and false", () => {
    expect(toCsv(table([{ name: "in_fit", values: [true, false] }]))).toBe(
      "in_fit\r\ntrue\r\nfalse\r\n",
    );
  });

  it("refuses a non-finite number rather than writing it", () => {
    expect(() => toCsv(table([{ name: "x", values: [NaN] }]))).toThrow(/non-finite/);
    expect(() => toCsv(table([{ name: "x", values: [Infinity] }]))).toThrow(/non-finite/);
  });

  describe("formula-injection guard", () => {
    it.each([
      ["=SUM(A1)", "'=SUM(A1)"],
      ["+1", "'+1"],
      ["@x", "'@x"],
      ["-cmd", "'-cmd"],
      ["\tx", "'\tx"],
    ])("prefixes the text %j with a quote mark", (text, expected) => {
      expect(toCsv(table([{ name: "a", values: [text] }]))).toBe(`a\r\n${expected}\r\n`);
    });

    it("prefixes text starting with a carriage return, then quotes it", () => {
      expect(toCsv(table([{ name: "a", values: ["\rx"] }]))).toBe('a\r\n"\'\rx"\r\n');
    });

    it("never prefixes a number, so -3.2 stays -3.2", () => {
      expect(toCsv(table([{ name: "a", values: [-3.2] }]))).toBe("a\r\n-3.2\r\n");
    });

    it("guards headers too (column names can come from a user's file)", () => {
      expect(toCsv(table([{ name: "=cmd", values: [] }]))).toBe("'=cmd\r\n");
    });

    it("prefixes, then quotes, text that also needs quoting", () => {
      expect(toCsv(table([{ name: "a", values: ['=HYPERLINK("x")'] }]))).toBe(
        'a\r\n"\'=HYPERLINK(""x"")"\r\n',
      );
    });

    it("leaves ordinary text alone", () => {
      expect(toCsv(table([{ name: "a", values: ["height-1"] }]))).toBe("a\r\nheight-1\r\n");
    });
  });
});

describe("csvFilename", () => {
  it("is the model id, the first 8 characters of the run id and the table", () => {
    expect(
      csvFilename("physics.projectile", "0123abcd-4567-89ef-0123-456789abcdef", "trajectory"),
    ).toBe("physics.projectile_0123abcd_trajectory.csv");
  });
});
