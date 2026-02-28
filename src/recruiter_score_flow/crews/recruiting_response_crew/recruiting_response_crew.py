from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task 

@CrewBase 
class RecruitingResponseCrew: 

    agents_config = "config/agents.yaml" 
    tasks_config = "config/tasks.yaml"  

    @agent 
    def email_followup_agent(self) -> Agent: 
        return Agent(
            config = self.agents_config["email_followup_agent"], 
            verbose = False, 
            allow_delegation = False 
        )   
    
    @task 
    def send_email_followup_task(self) -> Task: 
        return Task(
            config = self.tasks_config["send_followup_email"], 
            verbose = False
        ) 
    
    @crew
    def crew(self) -> Crew: 
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    

    