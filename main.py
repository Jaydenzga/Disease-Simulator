import streamlit as st
import matplotlib.pyplot as plt

population = st.slider("Population", 100, 10000, 1000)
initial_infected = st.slider("Initial Infected", 1, 100, 2)
infection_rate = st.slider("Infection Rate", 0.01, 0.5, 0.05)
recovery_rate = st.slider("Recovery Rate", 0.01, 0.5, 0.03)
days = st.slider("Days", 10, 200, 30)




#to add: reinfection, deaths, vaccine effectiveness,

vaccination_percentage = st.slider("Vaccinated (%)", 0, 100, 0)
vaccinated = population * (vaccination_percentage / 100)
infected = initial_infected
recovered = 0
suseptible = population - infected

infected_list = []
suseptible_list = []
recovered_list = []
vaccinated_list = []

for day in range(days): 
    new_infections = (infected * infection_rate) * (suseptible / population)
    new_recoveries = infected * recovery_rate

    suseptible -= new_infections
    infected = infected + new_infections - new_recoveries
    recovered += new_recoveries

    infected_list.append(infected)
    suseptible_list.append(suseptible)
    recovered_list.append(recovered)
    vaccinated_list.append(vaccinated)



fig, ax = plt.subplots()

ax.plot(infected_list, label="Infected", color="red")
ax.plot(recovered_list, label="Recovered", color="green")
ax.plot(suseptible_list, label="Susceptible", color="blue")
ax.plot(vaccinated_list, label="Vaccinated", color="purple")

ax.set_title("Disease Spread (SIR Model)")
ax.set_xlabel("Days")
ax.set_ylabel("People")
ax.legend()

st.pyplot(fig)

