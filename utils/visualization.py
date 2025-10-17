import matplotlib.pyplot as plt
import os

def plot_performance(sequential_time, parallel_time):
    """Vẽ biểu đồ so sánh hiệu năng"""
    labels = ['Sequential', 'Parallel']
    times = [sequential_time, parallel_time]

    plt.figure(figsize=(8, 5))
    plt.bar(labels, times, color=['#ff9999', '#66b3ff'])
    plt.ylabel('Thời gian (giây)')
    plt.title('So Sánh Hiệu Năng Xử Lý Tuần Tự vs Song Song')
    plt.savefig('static/results/performance_plot.png')
    plt.close()