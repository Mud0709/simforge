# Where these skills come from

Project skills load automatically in every Claude Code session opened in this repository.

| Skill | Source | Licence | Changes |
|---|---|---|---|
| `systematic-debugging` | [obra/superpowers](https://github.com/obra/superpowers) `skills/systematic-debugging` at `b739a8a` | MIT, (c) 2025 Jesse Vincent | Two references renamed to the skills installed here; its internal test-scenario files were not copied |
| `verification-before-completion` | obra/superpowers `skills/verification-before-completion` at `b739a8a` | MIT, (c) 2025 Jesse Vincent | None |
| `tdd` | [mattpocock/skills](https://github.com/mattpocock/skills) `skills/engineering/tdd` at `5beb35b` | MIT, (c) 2026 Matt Pocock | Points to SimForge's test standards; two references to skills not installed here replaced (marked "SimForge adaptation") |
| `grilling` | mattpocock/skills `skills/productivity/grilling` at `5beb35b` | MIT, (c) 2026 Matt Pocock | None |
| `simforge-status` | Written for SimForge | Project licence | — |

Deliberately not installed: the full Superpowers plugin (its session-start hook makes skill
use compulsory on every message and costs tokens every session), terse-output "token
saving" skills (they conflict with explanations meant for learning), and broad skill packs
whose overlap with `CLAUDE.md` would only add noise.

Both upstream repositories are under the MIT licence, which permits copying and modification
provided the copyright notice and permission notice are kept:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this
> software and associated documentation files (the "Software"), to deal in the Software
> without restriction, including without limitation the rights to use, copy, modify, merge,
> publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
> to whom the Software is furnished to do so, subject to the following conditions: The above
> copyright notice and this permission notice shall be included in all copies or substantial
> portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
> EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
> FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
> HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
> CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
> USE OR OTHER DEALINGS IN THE SOFTWARE.
