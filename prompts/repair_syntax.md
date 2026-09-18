# Repair Process IR Syntax & Schema Prompt

The previously generated Process IR JSON failed automated schema validation or parsing.

## Validation Errors Encountered
```
{{VALIDATION_ERRORS}}
```

## Attempted JSON
```json
{{INVALID_JSON}}
```

## Correction Instructions
1. Fix all validation errors listed above.
2. Ensure all IDs are valid NCNames (no spaces, no illegal symbols, must start with letter or underscore).
3. Ensure every element has a valid `type` matching: startEvent, endEvent, intermediateTimerEvent, intermediateMessageEvent, task, userTask, serviceTask, manualTask, sendTask, receiveTask, exclusiveGateway, parallelGateway, inclusiveGateway, subProcess, callActivity.
4. Ensure every flow points to valid `sourceId` and `targetId` existing in `elements`.
5. Return ONLY the corrected, valid JSON object without surrounding text.
