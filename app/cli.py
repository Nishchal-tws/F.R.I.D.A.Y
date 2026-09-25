import asyncio
import json

from app.services.agent import FridayAgent


class FRIDAYCLI:
    ''' A class for CLI interaction with the friday agent
    @owner: Nischal Sharma
    @since : 23 sept 2026
    '''
    def __init__(self):
        self.agent = FridayAgent(approval_fn=self.approval_prompt)

    async def approval_prompt(self, tool: str, arguments: dict) -> bool:
        """Ask the operator at the terminal. Anything but an explicit yes is no."""
        print("\n[FRIDAY APPROVAL REQUIRED]")
        print(f"Tool: {tool}")
        print(json.dumps(arguments, indent=2))
        # input() blocks; keep it off the event loop so the agent stays responsive.
        answer = await asyncio.to_thread(input, "\nApprove? [y/N]: ")
        return answer.strip().lower() in {"y", "yes"}


async def main():
    cli = FRIDAYCLI()
    print("FRIDAY v0.1 online and ready to assist you")
    print("LLM:", cli.agent.llm.model)
    print("Ollama:", cli.agent.llm.base_url)
    print("Workspace:", cli.agent.context.workspace)
    print("Type 'exit' to quit.")

    try:
        data = await cli.agent.llm.health()
        models = {item.get("name") for item in data.get("models", [])}
        if cli.agent.llm.model not in models:
            print(f"\nWARNING: model '{cli.agent.llm.model}' is not installed locally.")
            print(f"Run: ollama pull {cli.agent.llm.model}")
    except Exception as exc:
        print("\nWARNING: local Ollama is not reachable.")
        print("Start Ollama and make sure its local API is available at 127.0.0.1:11434")
        print("Details:", exc)

    while True:
        try:
            user = (await asyncio.to_thread(input, "\nYou > ")).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            break

        try:
            answer = await cli.agent.chat(user)
            print("\nFRIDAY >", answer)
            if cli.agent.tool_events:
                print("\nTool events:")
                for event in cli.agent.tool_events:
                    print(json.dumps(event, indent=2))
        except Exception as exc:
            print("\nFRIDAY ERROR >", exc)


if __name__ == "__main__":
    asyncio.run(main())
