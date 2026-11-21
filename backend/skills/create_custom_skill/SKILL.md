---
name: create_custom_skill
description: Useful when the user wants to distill a workflow, create a new skill, or package a task sequence into a reusable custom skill.
---

# Create Custom Skill

Use this skill when you need to package a workflow, set of instructions, or a sequence of steps into a new reusable custom agent skill.

## Steps

1. **Define Skill Name and Description**:
   - The name should be short and use `snake_case` (e.g., `github_repo_setup`).
   - The description should clearly state when this skill should be triggered.

2. **Determine the Location**:
   - All custom skills must be created in a new subdirectory under:
     `d:/Codes/agents/skills/<skill_name>/SKILL.md`

3. **Format the Frontmatter**:
   - The `SKILL.md` file MUST start with a frontmatter block containing `name` and `description` exactly as follows:
     ```yaml
     ---
     name: <skill_name>
     description: <description>
     ---
     ```

4. **Write the Skill Body**:
   - Add a main heading `# <Skill Name>`
   - Document any prerequisites required for the skill.
   - Outline the concrete steps, including commands, file edits, or tool calls needed to execute the workflow.

5. **Write the File**:
   - Use `write_to_file` to write the new `SKILL.md` file to `d:/Codes/agents/skills/<skill_name>/SKILL.md`. Set `Overwrite: true` if updating an existing one.
