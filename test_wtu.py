#!/usr/bin/env python3
import asyncio
from app.metrics import calculate_wtu, count_tokens

async def test_wtu():
    # WTU 계산 테스트
    input_tokens = 100
    output_tokens = 50
    embed_tokens = 1000

    print("=== WTU 계산 테스트 ===")

    # 텍스트 생성 WTU 계산
    text_wtu, text_cost = await calculate_wtu(
        in_tokens=input_tokens, 
        out_tokens=output_tokens, 
        llm_model='gpt-3.5-turbo'
    )
    print(f"텍스트 생성 - Input: {input_tokens}, Output: {output_tokens} tokens → {text_wtu} WTU (${text_cost:.4f})")

    # 임베딩 WTU 계산  
    embed_wtu, embed_cost = await calculate_wtu(
        embed_tokens=embed_tokens, 
        embedding_model='text-embedding-3-small'
    )
    print(f"임베딩 - Embed: {embed_tokens} tokens → {embed_wtu} WTU (${embed_cost:.4f})")

    # 토큰 계산 테스트
    print("\n=== 토큰 계산 테스트 ===")
    text = "안녕하세요. 이것은 테스트 텍스트입니다."
    model = 'gpt-3.5-turbo'
    tokens = count_tokens(text, model)
    print(f"Text: {text}")
    print(f"Model: {model}")
    print(f"Tokens: {tokens}")

if __name__ == "__main__":
    asyncio.run(test_wtu())
