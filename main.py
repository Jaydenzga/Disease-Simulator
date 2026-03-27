import matplotlib.pyplot as plt

population = 1000
infected = 2
recovered = 0

infection_rate = 0.05
recovery_rate = 0.03

days = 30

infected_list = []

for day in range(days): 
    new_infections = infected * recovery_rate
    new_recoveries = infected * recovery_rate

    infected = infected + new_infections - new_recoveries
    recovered += new_recoveries

    infected_list.append(infected)


plt.plot(infected_list)
plt.title("Disease Spread Over Time")
plt.xlabel("Days")
plt.ylabel("Infected People")
plt.show()