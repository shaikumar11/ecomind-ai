"""Smoke test for EcoMind AI's RAG engine — run with: python test_rag.py"""

from rag import EcoMindRAG, estimate_footprint

def main():
    rag = EcoMindRAG()
    print(f"Loaded knowledge base with {len(rag.kb)} entries.\n")

    queries = [
        "how can I lower my electricity bill",
        "best way to reduce food waste",
        "is an electric car actually better for the climate",
        "how do I help pollinators in my garden",
        "what's the capital of France",  # expected: no confident match
    ]

    for q in queries:
        result = rag.answer(q)
        print(f"Q: {q}")
        print(f"A: {result['answer']}")
        print(f"Sources: {result['sources']}")
        print(f"Matched entries: {result['matched_entries']}")
        print("-" * 70)

    print("\nFootprint estimate example:")
    fp = estimate_footprint(
        rag, car_km_week=120, elec_kwh_month=250,
        diet="average", short_flights=1, long_flights=0,
    )
    print(fp)


if __name__ == "__main__":
    main()
