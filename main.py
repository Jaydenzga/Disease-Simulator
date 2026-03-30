import matplotlib.pyplot as plt

population = 1000
infected = 2
recovered = 0
suseptible = population - infected

infection_rate = 0.05
recovery_rate = 0.03

days = 30

infected_list = []
suseptible_list = []
recovered_list = []

for day in range(days): 
    new_infections = infected * infection_rate * (suseptible / population)
    new_recoveries = infected * recovery_rate

    suseptible -= new_infections
    infected = infected + new_infections - new_recoveries
    recovered += new_recoveries

    infected_list.append(infected)
    suseptible_list.append(suseptible)
    recovered_list.append(recovered)


plt.plot(infected_list, label="Infected", color="red")
plt.plot(recovered_list, label="Recovered", color="green")
plt.plot(suseptible_list, label="Susceptible", color="blue")

plt.title("Disease Spread Over Time")
plt.xlabel("Days")
plt.ylabel("Infected People")
plt.legend()
plt.show()