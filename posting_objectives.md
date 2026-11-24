# LinkedIn posting objectives

## Main message

This is an observable CAD/BIM assistant: deterministic code handles files, previews, and data lookups; the LLM explains the results. Think of the code as the measuring tools and the LLM as the guide reading the measurements.

Do not call the LLM itself deterministic. Call the **workflow**, file processing, and tool calls deterministic.

## Safe claims: already implemented in code

- **IFC and CAD preview pipeline:** IFC files can be viewed, while STEP/STP files are converted on the server into GLB files for 3D preview.
- **Deterministic workflow:** file type selects a repeatable ingestion path and a set of checks; regular code retrieves project data, while the LLM explains those results.
- **Monitoring and tracing:** OpenTelemetry/OpenInference traces capture an agent run, LLM calls, tool calls, and the final answer. Traces are stored locally in `data/traces/traces.jsonl` and can be downloaded through `/traces`.
- **Real evaluation scores:** bundled STEP sample checks score whether each source file and its browser preview actually exist. STEP answer checks also catch invented thread/standard/material claims.
- **Monitoring dashboard:** `/monitoring` shows real local trace counts, errors, response time, tool calls, recent runs, and repeatable sample-file scores.
- **STEP-aware answer safety:** prompts tell the agent that STEP/STP is CAD geometry, while IFC may contain structured BIM facts. It must not invent bolt standards, thread pitch, materials, cost, or schedules.
- **Threaded-bolt sample:** a separate `ThreadedHexBolt.step` and GLB preview are included beside the plain bolt sample.
- **Chat memory:** the last 12 chat turns are sent with the next question and saved in the browser for each project.
- **Basic automated tests:** repository and agent-tool tests already exist.

## Honest limits to mention

- The evaluation scorecard checks specific, transparent rules. It is not a claim that every possible AI answer is correct.
- The monitoring dashboard reads the app's local trace file. For a public production service, send traces to a managed monitoring system too.

## Best post structure

1. **Architecture image:** IFC/STEP/STP upload -> deterministic preview/data tools -> LLM explanation -> traces.
2. **Proof image:** one trace showing a question, the tool calls, and answer.
3. **Tiny evaluation table:** use it as the next milestone: sample file, expected result, actual result, pass/fail.

Suggested headline: **"Building an observable CAD/BIM assistant: deterministic geometry pipeline, tool-using LLM, and trace-first evaluation."**

## Next evaluation design

Use fixed sample cases: an IFC building, a plain STEP bolt, and a threaded STEP bolt. For each case, automatically check that the file loads, a 3D preview appears, the file type is correctly identified, and the answer does not invent missing properties. That is like marking an exam with an answer key, instead of trusting that every answer merely sounds clever.
