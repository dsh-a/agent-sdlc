# Customer profiles — <product>

Copy this file to the path `customer_profiles_path` names in `.omp/agent-config.md` (default
`product/customer-profiles.md`, which is **vault**-class), then replace every profile below with
your own. `/refine`'s `profile-impact` probe reads it; until it holds at least one profile that
is not called `Template`, the probe reports **`unavailable`** and refinement says so in the log
rather than reporting the perspective clean.

**One `##` heading per profile, with all four fields.** The parser is
`probes.py profiles --path <file>`; run it after editing and check `incomplete=0`.

| Field | What it is for |
|---|---|
| `Goal` | what they are trying to achieve, in their words, not the product's |
| `Session shape` | how long, how often, how much they do in one sitting |
| `Data volume` | how much of your data they accumulate — the worst case has to belong to someone |
| `Breaks when` | the condition under which the product stops working for them. **This is the field the `degrades` verdict reads**, so it has to be falsifiable, not a sentiment |

Three to five profiles. Two is usually one profile and its absence; more than five and nobody
remembers them, which is the same as having none.

**Prose sections are fine.** A `##` section carrying none of the four fields is skipped as prose
and reported as such, so findings and caveats can live in this file beside the profiles. A section
carrying *some* of the fields is an incomplete profile and is flagged — the two are kept distinct
so a mistyped field name cannot pass as "not a profile".

The questions the probe asks, once this file exists:

- **Which profile is this story designed for?** "All of them equally" is the answer to distrust.
- **Which profile does it degrade?** A view built for the heaviest user is an empty screen for
  the newest one.
- **Which profile would never discover it?** Discovery differs by profile, and placement is an
  acceptance criterion.

---

## Template

- Goal:
- Session shape:
- Data volume:
- Breaks when:
