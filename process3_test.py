import asyncio
from browser_use import Agent
from browser_use.llm.anthropic.chat import ChatAnthropic
from computeruse import wrap, WrapConfig

async def main():
    llm = ChatAnthropic(model="claude-sonnet-4-6")
    agent = Agent(
        task="Go to https://news.ycombinator.com and get the titles of the top 5 posts",
        llm=llm,
    )
    wrapped = wrap(agent, WrapConfig(
        api_url="http://localhost:8000",
        api_key="cu_test_testkey1234567890abcdef12",
    ))
    result = await wrapped.run()
    
    print(f"Result: {result.final_result()}")
    print(f"Cost: ${wrapped.cost_cents / 100:.4f}")
    print(f"Steps: {len(wrapped.steps)}")
    print(f"Replay: {wrapped.replay_path}")

asyncio.run(main())
