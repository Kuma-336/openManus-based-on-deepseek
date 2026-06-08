import argparse
import asyncio

from app.agent.manus import Manus
from app.logger import logger


def _print_final_answer(agent):
    for msg in reversed(agent.memory.messages):
        if msg.role == "assistant" and msg.content and msg.content.strip():
            print("\n" + "=" * 60)
            print(msg.content.strip())
            print("=" * 60)
            break


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument(
        "--prompt", type=str, required=False, help="Input prompt for the agent"
    )
    args = parser.parse_args()

    # Create and initialize Manus agent
    agent = await Manus.create()
    try:
        # If a prompt is provided via command line, run once and exit
        if args.prompt:
            if not args.prompt.strip():
                logger.warning("Empty prompt provided.")
                return
            logger.warning("Processing your request...")
            await agent.run(args.prompt)
            logger.info("Request processing completed.")
            _print_final_answer(agent)
            return

        # Interactive multi-turn conversation loop
        print("Enter your prompt (type 'exit' or 'quit' to stop):")
        while True:
            try:
                prompt = input("\nYou: ").strip()
            except EOFError:
                break
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            logger.warning("Processing your request...")
            await agent.run(prompt)
            logger.info("Request processing completed.")
            _print_final_answer(agent)
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
