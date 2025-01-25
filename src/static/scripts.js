document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/chain');
        const data = await response.json();
        console.log(data);  // Добавляем вывод данных в консоль
        const chain = data.chain;
        const chainDiv = document.getElementById('chain');

        chain.forEach(block => {
            const blockDiv = document.createElement('div');
            blockDiv.classList.add('block');

            const blockIndex = document.createElement('h2');
            blockIndex.textContent = `Block #${block.index}`;
            blockDiv.appendChild(blockIndex);

            const blockPreviousHash = document.createElement('p');
            blockPreviousHash.innerHTML = `<strong>Previous Hash:</strong> ${block.previous_hash}`;
            blockDiv.appendChild(blockPreviousHash);

            const blockTimestamp = document.createElement('p');
            blockTimestamp.innerHTML = `<strong>Timestamp:</strong> ${block.timestamp}`;
            blockDiv.appendChild(blockTimestamp);

            const blockHash = document.createElement('p');
            blockHash.innerHTML = `<strong>Hash:</strong> ${block.hash}`;
            blockDiv.appendChild(blockHash);

            const blockTransactions = document.createElement('h3');
            blockTransactions.textContent = 'Transactions';
            blockDiv.appendChild(blockTransactions);

            const transactionsList = document.createElement('ul');
            block.transactions.forEach(tx => {
                const transactionItem = document.createElement('li');
                transactionItem.innerHTML = `<strong>${tx.sender}</strong> → <strong>${tx.recipient}</strong>: ${tx.amount} (Signature: ${tx.signature})`;
                transactionsList.appendChild(transactionItem);
            });
            blockDiv.appendChild(transactionsList);

            chainDiv.appendChild(blockDiv);
        });

        document.getElementById('createWallet').addEventListener('click', async () => {
            const response = await fetch('/wallet/new');
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const wallet = await response.json();
            console.log(wallet); // Добавляем вывод данных в консоль
            const walletsDiv = document.getElementById('wallets');
            const walletDiv = document.createElement('div');
            walletDiv.classList.add('wallet');

            const walletKeys = document.createElement('p');
            walletKeys.innerHTML = `<strong>Private Key:</strong> ${wallet.private_key}<br><strong>Public Key:</strong> ${wallet.public_key}`;
            walletDiv.appendChild(walletKeys);

            const balanceButton = document.createElement('button');
            balanceButton.textContent = 'Check Balance';
            balanceButton.addEventListener('click', async () => {
                const response = await fetch('/wallet/balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ public_key: wallet.public_key })
                });
                const balance = await response.json();
                const balanceDiv = document.createElement('p');
                balanceDiv.innerHTML = `<strong>Balance:</strong> ${balance.balance}`;
                walletDiv.appendChild(balanceDiv);
            });
            walletDiv.appendChild(balanceButton);

            walletsDiv.appendChild(walletDiv);
        });

        document.getElementById('mineBlock').addEventListener('click', async () => {
            const minerAddress = document.getElementById('minerAddress').value;
            const response = await fetch('/mine', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ miner_address: minerAddress })
            });
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const result = await response.json();
            console.log(result);
            window.location.reload(); // Перезагрузить страницу, чтобы обновить отображение блокчейна
        });
    } catch (error) {
    console.error('Error fetching blockchain data:', error);
    }
}); 