from apps.backend.src.states.evidence import InsuranceState,PolicySummary

class InsuranceNode:
    """
    A class representing an insurance node in the system.
    """

    def __init__(self,llm):
        self.llm=llm
        
    def get_policy_summary(self,state:InsuranceState)-> dict:
        """
        Get the policy summary for a given insurance state.

        Args:
            state (InsuranceState): The insurance state for which to get the policy summary.
        """

        policy_name=state.get("policy_name")

        if not policy_name:
            payload=state.get("policy_summary")
            if isinstance(payload,dict):
                policy_name=payload.get("policy_name")
            elif isinstance(payload,PolicySummary):
                policy_name=getattr(payload,"policy_name",None)
        
        if not policy_name or not isinstance(policy_name,str):
            raise ValueError(
                "Missing or invalid policy_name. Expected either "
                "{'policy_name': 'Name of the insurance policy'} or "
                "{'policy_summary': {'policy_name': 'Name of the insurance policy'}}"
            )
        
        prompt = (
                    f"You are an expert insurance assistant. Provide a concise, factual summary "
                    f"of the key benefits and features of the health insurance policy: {policy_name}. "
                    f"If you recognize the brand, use your knowledge to be specific."
                )
        
        # Use the LLM to generate a summary for the given policy name
        response=self.llm.invoke(prompt)

        summary_text=getattr(response,"content",str(response))

        result = PolicySummary(
            policy_name=policy_name,
            policy_summary=summary_text
        )

        if hasattr(result,"model_dump"):
            summary_obj=result.model_dump()
        else:
            summary_obj=result.dict()

        return {"policy_summary": summary_obj}

