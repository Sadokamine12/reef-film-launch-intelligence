# Audit and consolidation of the uploaded project

The uploaded project was reviewed as a complete codebase before V11 was assembled. The purpose of this file is to record the major structural issues that were removed so the project does not continue as an endless patch chain.

## Issues found in the uploaded version

1. **Multiple overlapping ML implementations**
   - Some modules still imported scikit-learn even though Windows Application Control blocks its compiled DLLs.
   - Other modules used the newer numpy/pandas trainer.
   - Result: different pages could use different modeling logic.

2. **Old project identity still present**
   - Documentation still referred to a Munich kids-film MVP even though the real project is Resolution at ESO for adults 20–60.

3. **Fragmented configuration**
   - Several Resolution/ESO config files coexisted, creating a risk that one collector/page used different dates, budget, or target audience.

4. **Streamlit page placement drift**
   - Later Model Training / Quality / Campaign Lab scripts were not consistently located inside the `pages` folder.

5. **Duplicate ESO evidence**
   - English and German public URLs could refer to the same ESO booking ID, inflating rows and weakening validation.

6. **Validation leakage risk**
   - Row-wise validation looked much stronger because repeated snapshots from the same show could appear in both training and validation.
   - V11 uses grouped-by-show validation for the demand model.

7. **Marketing causality was not sufficiently gated**
   - Earlier scenario priors could look like learned geo/channel/creative effects even before real campaign labels existed.
   - V11 only calls ticket-lift ML operational after verified labels and quality gates.

8. **No single complete experiment plan**
   - Previous versions added tests incrementally.
   - V11 defines the full EUR 500 test-and-scale protocol before spending starts.

## V11 consolidation decisions

- One config: `config/project.json`
- One Windows-safe ML backend: numpy/pandas + JSON artifacts
- One canonical ESO booking ID per performance
- One canonical campaign schema
- One explicit attribution hierarchy
- One model-governance rule: weak models do not drive operational recommendations
- One complete EUR 500 experiment protocol
- One project doctor to catch missing data/contracts/pages before use
- One daily update command
- One dashboard start command

## Current evidence after canonical migration

The supplied ESO snapshot data was canonicalized from 28 rows to 26 rows across 13 unique public bookings. The current grouped-by-show lightweight model is trained but remains below the configured operational quality gate. V11 therefore uses the empirical PAVA baseline for current operational demand scenarios while continuing to show ML quality for research and improvement.

This is expected behavior, not a missing module.
