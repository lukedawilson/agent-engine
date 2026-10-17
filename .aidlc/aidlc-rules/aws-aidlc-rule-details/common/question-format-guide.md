# Question Format Guide

## MANDATORY: All Questions Must Use This Format

### Rule: Always Ask Questions Inline in Chat
**CRITICAL**: You MUST ask questions directly in the chat using the question tool or inline interaction. After the user answers, write their answers back to the corresponding plan file's `[Answer]:` tags so the file serves as the authoritative record. Do NOT ask the user to edit files directly.

### Question File Format

#### File Naming Convention
- Use descriptive names: `{phase-name}-questions.md`
- Examples:
  - `classification-questions.md`
  - `requirements-questions.md`
  - `story-planning-questions.md`
  - `design-questions.md`

#### Question Structure
Every question must include meaningful options plus "Other" as the last option:

```markdown
## Question [Number]
[Clear, specific question text]

A) [First meaningful option]

B) [Second meaningful option]

[...additional options as needed...]

X) Other (please describe after [Answer]: tag below)

[Answer]: 
```

**CRITICAL**:
- "Other" is MANDATORY as the LAST option for every question
- Only include meaningful options - don't make up options to fill slots
- Use as many or as few options as make sense (minimum 2 + Other)
- **Each option must be separated by a blank line** so strict CommonMark renderers (IntelliJ, PyCharm, etc.) display them on separate lines instead of collapsing them into a single paragraph

### Complete Example

```markdown
# Requirements Clarification Questions

Please answer the following questions to help clarify the requirements.

## Question 1
What is the primary user authentication method?

A) Username and password

B) Social media login (Google, Facebook)

C) Single Sign-On (SSO)

D) Multi-factor authentication

E) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
Will this be a web or mobile application?

A) Web application

B) Mobile application

C) Both web and mobile

D) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
Is this a new project or existing codebase?

A) New project (greenfield)

B) Existing codebase (brownfield)

C) Other (please describe after [Answer]: tag below)

[Answer]: 
```

### User Response Format
Users will answer by filling in the letter choice after [Answer]: tag:

```markdown
## Question 1
What is the primary user authentication method?

A) Username and password

B) Social media login (Google, Facebook)

C) Single Sign-On (SSO)

D) Multi-factor authentication

[Answer]: C
```

### Reading User Responses
After user confirms completion:
1. Read the question file
2. Extract answers after [Answer]: tags
3. Validate all questions are answered
4. Proceed with analysis based on responses

### Multiple Choice Guidelines

#### Option Count
- Minimum: 2 meaningful options + "Other" (A, B, C)
- Typical: 3-4 meaningful options + "Other" (A, B, C, D, E)
- Maximum: 5 meaningful options + "Other" (A, B, C, D, E, F)
- **CRITICAL**: Don't make up options just to fill slots - only include meaningful choices

#### Option Quality
- Make options mutually exclusive
- Cover the most common scenarios
- Only include meaningful, realistic options
- **ALWAYS include "Other" as the LAST option** (MANDATORY)
- Be specific and clear
- **Don't make up options to fill A, B, C, D slots**

#### Good Example:
```markdown
## Question 5
What database technology will be used?

A) Relational (PostgreSQL, MySQL)

B) NoSQL Document (MongoDB, DynamoDB)

C) NoSQL Key-Value (Redis, Memcached)

D) Graph Database (Neo4j, Neptune)

E) Other (please describe after [Answer]: tag below)

[Answer]: 
```

#### Bad Example (Avoid):
```markdown
## Question 5
What database will you use?

A) Yes

B) No

C) Maybe

[Answer]: 
```

### Workflow Integration

#### Step 1: Create Plan/Question File
Create the stage plan file at the appropriate path (e.g., `aidlc-docs/construction/plans/{unit-name}-functional-design-plan.md`) with embedded `[Answer]:` tags.

#### Step 2: Ask Questions Inline
Present all questions to the user inline in the chat using the question tool or direct interaction, one at a time or in batches. Reference the plan file location so the user knows where answers will be recorded.

#### Step 3: Collect Answers
Collect user responses directly in the chat interaction.

#### Step 4: Write Answers Back
After collecting all answers, write them back to the plan file's `[Answer]:` tags so the file becomes the authoritative record. This ensures the file is always up-to-date.

#### Step 5: Validate and Analyze
Validate completeness (all questions answered), check for contradictions/ambiguities, and proceed with analysis.

### Error Handling

#### Missing Answers
If the user hasn't answered a question, ask for it specifically inline before proceeding.

#### Invalid Answers
If the user's answer doesn't match any option, clarify inline and ask them to choose from the available options.

#### Ambiguous Answers
If the user provides a vague response, ask a clarifying follow-up question inline before writing the answer back.

### Contradiction and Ambiguity Detection

**MANDATORY**: After reading user responses, you MUST check for contradictions and ambiguities.

#### Detecting Contradictions
Look for logically inconsistent answers:
- Scope mismatch: "Bug fix" but "Entire codebase affected"
- Risk mismatch: "Low risk" but "Breaking changes"
- Timeline mismatch: "Quick fix" but "Multiple subsystems"
- Impact mismatch: "Single component" but "Significant architecture changes"

#### Detecting Ambiguities
Look for unclear or borderline responses:
- Answers that could fit multiple classifications
- Responses that lack specificity
- Conflicting indicators across multiple questions

#### Creating Clarification Questions
If contradictions or ambiguities detected:

1. **Create clarification file**: `{phase-name}-clarification-questions.md`
2. **Explain the issue**: Clearly state what contradiction/ambiguity was detected
3. **Ask targeted questions**: Use multiple choice format to resolve the issue
4. **Reference original questions**: Show which questions had conflicting answers

**Example**:
```markdown
# [Phase Name] Clarification Questions

I detected contradictions in your responses that need clarification:

## Contradiction 1: [Brief Description]
You indicated "[Answer A]" (Q[X]:[Letter]) but also "[Answer B]" (Q[Y]:[Letter]).
These responses are contradictory because [explanation].

### Clarification Question 1
[Specific question to resolve contradiction]

A) [Option that resolves toward first answer]

B) [Option that resolves toward second answer]

C) [Option that provides middle ground]

D) [Option that reframes the question]

[Answer]: 

## Ambiguity 1: [Brief Description]
Your response to Q[X] ("[Answer]") is ambiguous because [explanation].

### Clarification Question 2
[Specific question to clarify ambiguity]

A) [Clear option 1]

B) [Clear option 2]

C) [Clear option 3]

D) [Clear option 4]

[Answer]: 
```

#### Workflow for Clarifications

1. **Detect**: Analyze all responses for contradictions/ambiguities
2. **Create**: Generate clarification question file if issues found
3. **Inform**: Tell user about the issues and clarification file
4. **Wait**: Do not proceed until user provides clarifications
5. **Re-validate**: After clarifications, check again for consistency
6. **Proceed**: Only move forward when all contradictions are resolved

#### Example User Message
```
"I detected 2 contradictions in your responses:

1. Bug fix scope vs. codebase impact (Q1 vs Q2)
2. Low risk vs. breaking changes (Q7 vs Q4)

I've created classification-clarification-questions.md with 2 questions to resolve these.
Please answer these clarifying questions before I can proceed with classification."
```

### Best Practices

1. **Be Specific**: Questions should be clear and unambiguous
2. **Be Comprehensive**: Cover all necessary information
3. **Be Concise**: Keep questions focused on one topic
4. **Be Practical**: Options should be realistic and actionable
5. **Be Consistent**: Use same format throughout all question files

### Phase-Specific Examples

#### Example with 2 meaningful options:
```markdown
## Question 1
Is this a new project or existing codebase?

A) New project (greenfield)

B) Existing codebase (brownfield)

C) Other (please describe after [Answer]: tag below)

[Answer]: 
```

#### Example with 3 meaningful options:
```markdown
## Question 2
What is the deployment target?

A) Cloud (AWS, Azure, GCP)

B) On-premises servers

C) Hybrid (both cloud and on-premises)

D) Other (please describe after [Answer]: tag below)

[Answer]: 
```

#### Example with 4 meaningful options:
```markdown
## Question 3
What architectural pattern should be used?

A) Monolithic architecture

B) Microservices architecture

C) Serverless architecture

D) Event-driven architecture

E) Other (please describe after [Answer]: tag below)

[Answer]: 
```

## Summary

**Remember**: 
- ✅ Always create question/plan files with [Answer]: tags
- ✅ Always ask questions inline in chat
- ✅ Always write answers back to the plan file after collecting them
- ✅ Always use multiple choice format
- ✅ **Always include "Other" as the LAST option (MANDATORY)**
- ✅ Only include meaningful options - don't make up options to fill slots
- ✅ Always use [Answer]: tags
- ✅ Always wait for user completion
- ✅ Always validate responses for contradictions
- ✅ Always create clarification files if needed
- ✅ Always resolve contradictions before proceeding
- ❌ Never ask the user to edit plan files directly to answer questions
- ❌ Never make up options just to have A, B, C, D
- ❌ Never proceed without answers
- ❌ Never proceed with unresolved contradictions
- ❌ Never make assumptions about ambiguous responses
