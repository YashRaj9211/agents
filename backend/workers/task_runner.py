"""Background worker to consume from task queue."""
from __future__ import annotations

import asyncio

# async def run_worker():
#     """
#     Stub: picks tasks from DB queue, runs skill, updates status.
#     Will use DB-backed queue, one browser agent per task.
#     """
#     while True:
#         # task = await get_next_task()
#         # if task:
#         #     skill = load_skill(task.skill_name)
#         #     agent = BrowserAgent(task.goal, skill=skill)
#         #     await skill.run(task.config, agent)
#         await asyncio.sleep(5)
#
# if __name__ == "__main__":
#     asyncio.run(run_worker())
