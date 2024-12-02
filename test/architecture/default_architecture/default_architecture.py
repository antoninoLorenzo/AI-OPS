import json
from pathlib import Path

from tqdm import tqdm
from deepeval.metrics import (
    BaseConversationalMetric,
    ConversationCompletenessMetric,
    ConversationRelevancyMetric,
    KnowledgeRetentionMetric
)

from src.agent import Agent
from src.utils import get_logger
from test.architecture.commons import (
    setup_system_test_resources,
    load_tests,
    save_tests,
    check_conversations,
    generate_conversation,
    run_system_test,
    GeminiLLM
)

logger = get_logger(__name__)


def run_architecture_test(
    agent: Agent,
    gemini_llm: GeminiLLM,
    test_case_path: str = 'default_architecture'
):
    print('[+] Loading evaluation resources')
    if check_conversations(test_case_path):
        print('[+] Generating Conversations')
        generate_conversation(
            test_case_path=test_case_path,
            agent=agent,
            gemini_llm=gemini_llm,
            max_turns=3
        )

    test_cases = load_tests(f'{test_case_path}_conversations.json')

    # defined metrics evaluate:
    # - Conversation Relevancy: the responses should at least be relevant
    # - Conversation Completeness: satisfy the user objectives
    # - Knowledge Retention: to address the context length problem
    metrics: dict[str, BaseConversationalMetric] = {
        'conversation_relevancy': ConversationRelevancyMetric(
            model=gemini_llm,
            threshold=0.7,
            include_reason=True
        ),
        'conversation_completeness': ConversationCompletenessMetric(
            model=gemini_llm,
            threshold=0.7,
            include_reason=True
        )
        # something's wrong with knowledge retention
        # 'knowledge_retention': KnowledgeRetentionMetric(
        #     model=gemini_llm,
        #     threshold=0.7,
        #     include_reason=True
        # )
    }

    print('[+] Running evaluation')
    run_system_test(
        test_cases=test_cases,
        metrics=metrics,
        agent_model=agent.agent.model
    )

    print('[+] Saving results')
    save_tests(
        tests=test_cases,
        name=f'{test_case_path}_out.json'
    )


if __name__ == "__main__":
    AGENT, JUDGE = setup_system_test_resources()
    run_architecture_test(AGENT, JUDGE)
