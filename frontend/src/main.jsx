import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { WagmiProvider } from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react'
import { WalletAdapterNetwork } from '@solana/wallet-adapter-base'
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui'
import { PhantomWalletAdapter, SolflareWalletAdapter } from '@solana/wallet-adapter-wallets'
import { clusterApiUrl } from '@solana/web3.js'
import { config } from './lib/wagmi'

// Solana wallet adapter CSS
import '@solana/wallet-adapter-react-ui/styles.css'

import App from './App.jsx'
import 'bootstrap/dist/css/bootstrap.min.css'

// Create a client for React Query
const queryClient = new QueryClient()

// Solana configuration
const network = WalletAdapterNetwork.Mainnet
const endpoint = clusterApiUrl(network)
const wallets = [
    new PhantomWalletAdapter(),
    new SolflareWalletAdapter()
]

createRoot(document.getElementById('root')).render(
    <StrictMode>
        <QueryClientProvider client={queryClient}>
            <WagmiProvider config={config}>
                <ConnectionProvider endpoint={endpoint}>
                    <WalletProvider wallets={wallets} autoConnect>
                        <WalletModalProvider>
                            <App />
                        </WalletModalProvider>
                    </WalletProvider>
                </ConnectionProvider>
            </WagmiProvider>
        </QueryClientProvider>
    </StrictMode>
)