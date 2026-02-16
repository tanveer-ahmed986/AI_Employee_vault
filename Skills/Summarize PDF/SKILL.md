# Skill: Summarize PDF

## When to Use

When a PDF file (.pdf) appears in /Needs_Action and needs to be reviewed and summarized. This skill handles PDFs specifically, including multi-page documents, and writes the summary to the accompanying .meta.md file.

## Trigger

- A `.pdf` file exists in /Needs_Action
- A matching `.pdf.meta.md` file exists alongside it (created by the File System Watcher)

## Steps

1. Read the `.pdf.meta.md` file to get metadata (source filename, detected date, priority)

2. Read the PDF file contents (all pages)

3. Identify the document type (report, guide, invoice, contract, presentation, etc.)

4. Analyze the full content and extract:
   - Main topic and purpose of the document
   - 3-7 key points (scaled to document length)
   - Any action items, deadlines, or follow-ups
   - Important names, numbers, or dates mentioned

5. Determine if the document contains sensitive content:
   - **Sensitive** (contracts, legal, financial, payments): Move to /Pending_Approval instead of /Done
   - **Non-sensitive** (guides, reports, informational): Continue to step 6

6. Write the summary to the `.pdf.meta.md` file:
   - Update `status:` from `pending` to `completed` in the frontmatter
   - Append a `## Summary` section at the bottom (see Output Format below)

7. Move both the `.pdf` and `.pdf.meta.md` files to /Done

8. Update Dashboard.md:
   - Increment "Completed Today" count
   - Add entry to "Recent Activity" with document name and brief description

9. Log the action in /Logs/[today].md with:
   - Document name and type
   - Page count
   - Priority level
   - Skills used
   - Result status

## Output Format

```
## Summary

**Overview:** [one sentence describing the document's purpose]

**Document Type:** [report / guide / invoice / contract / presentation / other]

**Page Count:** [number]

**Key Points:**

- [point 1]

- [point 2]

- [point 3]

- [point 4 if needed]

- [point 5 if needed]

**Important Details:**

- [names, dates, numbers, or deadlines worth noting]

**Action Items:**

- [ ] [action if any]

- [ ] [action if any]
```

## Edge Cases

- **PDF is unreadable or corrupted:** Write a note in the meta file stating the PDF could not be read. Move to /Pending_Approval for human review.
- **PDF contains only images (scanned):** Note that the document appears to be scanned/image-only and may need OCR. Move to /Pending_Approval.
- **PDF is very large (50+ pages):** Summarize in sections. Add a `## Section Summaries` block with per-section breakdowns before the overall summary.
- **No .meta.md file exists:** Create one using the standard meta template before proceeding.

## Example

Input: A 24-page hackathon guide PDF is dropped into /Needs_Action.

Output in `.pdf.meta.md`:
```
## Summary

**Overview:** A comprehensive hackathon blueprint for building autonomous AI employees using Claude Code and Obsidian.

**Document Type:** guide

**Page Count:** 24

**Key Points:**

- Four-layer architecture: Perception, Reasoning, Action, Persistence

- Digital FTE works 8,760 hrs/year at 85-90% cost savings vs human employees

- Tiered deliverables from Bronze (basic) to Platinum (always-on cloud)

- Human-in-the-loop safety via file-based approval workflow

**Important Details:**

- Weekly Research Meeting: Wednesdays at 10:00 PM on Zoom

- Required stack: Claude Code, Obsidian v1.10.6+, Python 3.13+, Node.js v24+

**Action Items:**

- [ ] Choose target tier (Bronze/Silver/Gold/Platinum)

- [ ] Install all prerequisites

- [ ] Set up Watcher scripts
```
