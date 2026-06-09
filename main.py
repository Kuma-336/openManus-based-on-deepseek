import argparse
import asyncio
from datetime import datetime

from app.agent.manus import Manus
from app.logger import logger
from app.memory.persistent import PersistentMemory


def _print_final_answer(agent):
    for msg in reversed(agent.memory.messages):
        if msg.role == "assistant" and msg.content and msg.content.strip():
            print("\n" + "=" * 60)
            print(msg.content.strip())
            print("=" * 60)
            break


def _pick_session() -> tuple[str, list]:
    """展示历史会话，返回 (session_id, 要预加载的消息列表)。"""
    sessions = PersistentMemory.list_sessions(limit=10)
    if not sessions:
        return datetime.now().strftime("%Y%m%d_%H%M%S"), []

    print("\n最近的对话记录：")
    for i, s in enumerate(sessions, 1):
        print(f"  [{i}] {s['started_at'][:16]}  ({s['msg_count']} 条消息)  {s['preview']}")
    print("  [0] 开始新对话")

    while True:
        choice = input("\n请选择（输入序号，默认 0）: ").strip()
        if choice == "" or choice == "0":
            return datetime.now().strftime("%Y%m%d_%H%M%S"), []
        if choice.isdigit() and 1 <= int(choice) <= len(sessions):
            s = sessions[int(choice) - 1]
            msgs = PersistentMemory.load_session(s["session_id"])
            print(f"已加载会话 {s['session_id']}，共 {len(msgs)} 条历史消息。")
            return s["session_id"], msgs
        print("输入无效，请重试。")


async def main():
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument("--prompt", type=str, required=False)
    args = parser.parse_args()

    agent = await Manus.create()
    try:
        # 命令行模式：单次运行，不加载历史
        if args.prompt:
            if not args.prompt.strip():
                logger.warning("Empty prompt provided.")
                return
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.warning("Processing your request...")
            await agent.run(args.prompt)
            logger.info("Request processing completed.")
            _print_final_answer(agent)
            PersistentMemory.save_messages(session_id, agent.memory.messages)
            return

        # 交互模式：选择历史会话或新建
        session_id, history = _pick_session()
        if history:
            agent.memory.messages = history

        print("\n输入你的问题（输入 exit 或 quit 退出）：")
        while True:
            try:
                prompt = input("\nYou: ").strip()
            except EOFError:
                break
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit"):
                print("再见！")
                break

            logger.warning("Processing your request...")
            await agent.run(prompt)
            logger.info("Request processing completed.")
            _print_final_answer(agent)
            PersistentMemory.save_messages(session_id, agent.memory.messages)

    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
