from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from recruiter_score_flow.schema.schema import CandidateScore 

@CrewBase 
class RecruitingScoreCrew: 

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml" 

    @agent 
    def hr_evaluation_agent(self) -> Agent: 
        return Agent(
            config = self.agents_config["hr_evaluation_agent"], 
            verbose = False
        ) 
    
    @task 
    def evaluate_candidate(self) -> Task:  
        return Task(
            config = self.tasks_config["evaluate_candidate"],  
            output_pydantic = CandidateScore, 
            verbose = False
        ) 
    
    @crew 
    def crew(self) -> Crew:
        return Crew(
            agents= self.agents, 
            tasks = self.tasks, 
            process = Process.sequential, 
            verbose = True
        )