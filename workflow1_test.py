import asyncio
from browser_use import Agent
from browser_use.llm.anthropic.chat import ChatAnthropic
from computeruse import wrap, WrapConfig

async def main():
    llm = ChatAnthropic(model="claude-sonnet-4-6")
    agent = Agent(
        task="Go to https://books.toscrape.com and get the titles and prices of the first 5 books",
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
    
    # Cost should NOT be $0.00 after O2-1 fix
    if wrapped.cost_cents == 0:
        print("⚠️  Cost is still $0 — O2-1 fix may not be working")
    else:
        print(f"✅ Cost tracking works: ${wrapped.cost_cents / 100:.4f}")
    
    # Check per-step tokens
    for i, step in enumerate(wrapped.steps):
        print(f"  Step {i}: {step.action_type} | tokens_in={step.tokens_in} tokens_out={step.tokens_out}")

asyncio.run(main())
