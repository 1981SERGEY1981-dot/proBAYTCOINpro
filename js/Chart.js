import { Chart } from 'chart.js';

const ctx = document.getElementById('myChart').getContext('2d');
const myChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['Январь', 'Февраль', 'Март', 'Апрель'],
        datasets: [{
            label: 'Пример графика',
            data: [10, 20, 30, 40],
            borderColor: 'rgba(75, 192, 192, 1)',
            fill: false
        }]
    },
    options: {
        scales: {
            x: { title: { display: true, text: 'Месяцы' } },
            y: { title: { display: true, text: 'Значение' } }
        }
    }
});

