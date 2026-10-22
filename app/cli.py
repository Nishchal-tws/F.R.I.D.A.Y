import asyncio
import json

from app.services.agent import FridayAgent

RED = "\033[31m"
RESET = "\033[0m"

BANNER = "\n".join((
    '=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=',
    '',
    '',
    '.           ..         .           .       .           .           .',
    '      .         .            .          .       .',
    '            .         ..xxxxxxxxxx....               .       .             .',
    '    .             MWMWMWWMWMWMWMWMWMWMWMWMW                       .',
    '              IIIIMWMWMWMWMWMWMWMWMWMWMWMWMWMttii:        .           .',
    ' .      IIYVVXMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWxx...         .           .',
    '     IWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMx..',
    '   IIWMWMWMWMWMWMWMWMWBY%ZACH%AND%OWENMWMWMWMWMWMWMWMWMWMWMWMWMx..        .',
    '    ""MWMWMWMWMWM"""""""".  .:..   ."""""MWMWMWMWMWMWMWMWMWMWMWMWMWti.',
    ' .     ""   . `  .: . :. : .  . :.  .  . . .  """"MWMWMWMWMWMWMWMWMWMWMWMWMti=',
    '        . .   :` . :   .  .\'.\' \'....xxxxx...,\'. \'   \' ."""YWMWMWMWMWMWMWMWMWMW+',
    '     ; . ` .  . : . .\' :  . ..XXXXXXXXXXXXXXXXXXXXx.    `     . "YWMWMWMWMWMWMW',
    '.    .  .  .    . .   .  ..XXXXXXXXWWWWWWWWWWWWWWWWXXXX.  .     .     """""""',
    '        \' :  : . : .  ...XXXXXWWW"   W88N88@888888WWWWWXX.   .   .       . .',
    '   . \' .    . :   ...XXXXXXWWW"    M88N88GGGGGG888^8M "WMBX.          .   ..  :',
    '         :     ..XXXXXXXXWWW"     M88888WWRWWWMW8oo88M   WWMX.     .    :    .',
    '           "XXXXXXXXXXXXWW"       WN8888WWWWW  W8@@@8M    BMBRX.         .  : :',
    '  .       XXXXXXXX=MMWW":  .      W8N888WWWWWWWW88888W      XRBRXX.  .       .',
    '     ....  ""XXXXXMM::::. .        W8@889WWWWWM8@8N8W      . . :RRXx.    .',
    '         ``...\'\'\'  MMM::.:.  .      W888N89999888@8W      . . ::::"RXV    .  :',
    " .       ..'''''      MMMm::.  .      WW888N88888WW     .  . mmMMMMMRXx",
    '      ..\' .            ""MMmm .  .       WWWWWWW   . :. :,miMM"""  : ""`    .',
    '   .                .       ""MMMMmm . .  .  .   ._,mMMMM"""  :  \' .  :',
    '               .                  ""MMMMMMMMMMMMM""" .  : . \'   .        .',
    '          .              .     .    .                      .         .',
    '.                                         .          .         .',
))


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
        answer = await asyncio.to_thread(input, "\nApprove? press 1 for yes\n 0 for no: ")
        return answer.strip().lower() in {"1"}


async def main():
    cli = FRIDAYCLI()
    print(f"{RED}{BANNER}{RESET}")
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
        except Exception as exc:
            print("\nFRIDAY ERROR >", exc)


if __name__ == "__main__":
    asyncio.run(main())
