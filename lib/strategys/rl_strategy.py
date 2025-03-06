import numpy as np
import gymnasium as gym
import os
from datetime import datetime, timedelta
from typing import List

from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from lib.model import Ohlcv
from lib.modules.strategyv2 import StrategyBase
from lib.utils.time import ts_to_dt


class StockTradingEnv(gym.Env):
    """A stock trading environment for OpenAI gym"""
    metadata = {'render.modes': ['human']}

    def __init__(self, ohlcv_data: List[Ohlcv], initial_balance=10000, transaction_fee_percent=0.001, window_size=10):
        super(StockTradingEnv, self).__init__()
        
        self.ohlcv_data = ohlcv_data
        self.initial_balance = initial_balance
        self.transaction_fee_percent = transaction_fee_percent
        self.window_size = window_size
        
        # Actions: 0 = Hold, 1 = Buy, 2 = Sell
        self.action_space = spaces.Discrete(3)
        
        # Observation space: [balance, shares_held, current_price] + historical price features
        self.observation_space = spaces.Box(
            low=0, high=np.inf, shape=(3 + 5 * window_size,), dtype=np.float32
        )
        
        self.reset()
    
    def _next_observation(self):
        # Get the price data points for the last window_size days
        frame = np.zeros((5 * self.window_size + 3,))
        
        # Set the first three values
        frame[0] = self.balance / self.initial_balance
        frame[1] = self.shares_held
        frame[2] = self.current_price
        
        # Extract OHLCV data for the window
        for i, j in enumerate(range(max(0, self.current_step - self.window_size + 1), self.current_step + 1)):
            if j >= 0:
                idx = i * 5
                frame[idx + 3] = self.ohlcv_data[j].open / self.current_price
                frame[idx + 4] = self.ohlcv_data[j].high / self.current_price
                frame[idx + 5] = self.ohlcv_data[j].low / self.current_price
                frame[idx + 6] = self.ohlcv_data[j].close / self.current_price
                frame[idx + 7] = self.ohlcv_data[j].volume / max(1, np.mean([x.volume for x in self.ohlcv_data]))
        
        return frame
    
    def _take_action(self, action):
        current_price = self.current_price
        
        if action == 1:  # Buy
            # Calculate maximum shares we can buy
            max_shares = self.balance / (current_price * (1 + self.transaction_fee_percent))
            # Buy all possible shares
            shares_bought = max_shares
            cost = shares_bought * current_price * (1 + self.transaction_fee_percent)
            
            self.balance -= cost
            self.shares_held += shares_bought
            self.total_shares_bought += shares_bought
            self.total_cost_basis += cost
            
        elif action == 2:  # Sell
            if self.shares_held > 0:
                # Sell all shares
                shares_sold = self.shares_held
                self.balance += shares_sold * current_price * (1 - self.transaction_fee_percent)
                self.shares_held = 0
                self.total_shares_sold += shares_sold
                self.total_sales_value += shares_sold * current_price
    
    def step(self, action):
        # Execute one time step within the environment
        self._take_action(action)
        
        self.current_step += 1
        
        if self.current_step >= len(self.ohlcv_data) - 1:
            self.current_step = len(self.ohlcv_data) - 1
        
        self.current_price = self.ohlcv_data[self.current_step].close
        
        # Calculate reward
        portfolio_value = self.balance + self.shares_held * self.current_price
        reward = (portfolio_value / self.initial_balance) - 1
        
        # Calculate done flag
        done = self.current_step >= len(self.ohlcv_data) - 1
        
        # Calculate info
        info = {
            'portfolio_value': portfolio_value,
            'step': self.current_step,
            'balance': self.balance,
            'shares_held': self.shares_held,
            'current_price': self.current_price
        }
        
        # Get the next observation
        obs = self._next_observation()
        
        return obs, reward, done, False, info
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # Reset the state of the environment to an initial state
        self.balance = self.initial_balance
        self.shares_held = 0
        self.current_step = 0
        self.current_price = self.ohlcv_data[self.current_step].close
        
        # Performance tracking
        self.total_shares_bought = 0
        self.total_cost_basis = 0
        self.total_shares_sold = 0
        self.total_sales_value = 0
        
        return self._next_observation(), {}
    
    def render(self, mode='human'):
        # Render the environment to the screen
        profit = self.balance + self.shares_held * self.current_price - self.initial_balance
        print(f'Step: {self.current_step}')
        print(f'Balance: {self.balance:.2f}')
        print(f'Shares held: {self.shares_held:.6f}')
        print(f'Current price: {self.current_price:.2f}')
        print(f'Profit: {profit:.2f}')
        print(f'Portfolio value: {self.balance + self.shares_held * self.current_price:.2f}')
        print('-' * 30)

def train_model(env, total_timesteps: int, log_path: str):
    """Train the PPO model"""
    model = PPO("MlpPolicy", env, verbose=1, tensorboard_log=log_path)
    model.learn(total_timesteps=total_timesteps)
    return model

class RlStrategy(StrategyBase):
    def __init__(self, model_path: str = None) -> None:
        self.window_size = 10
        self._data_fetch_amount = self.window_size + 1 
        self.model_path = model_path or '.'
        self.model_name = 'ppo_stock_trading'
        self.model: PPO = None

    def prepare_model(self):
        model_file_prefix = os.path.join(self.model_path, self.model_name)
        current_time = self.current_time
        
        for model_file in [f"{model_file_prefix}_{(current_time - timedelta(days=i)).strftime('%Y%m%d')}.zip" for i in range(10)]:
            if os.path.exists(model_file):
                self.model = PPO.load(model_file)
                return

        if self._is_test_mode:
            [start_time_in_ms, _] = self.state.get('bt_test_range')
            ohlcv_data_train = self.get_ohlcv_history(limit=50, end_time=ts_to_dt(start_time_in_ms))
        else:
            ohlcv_data_train = self.get_ohlcv_history(limit=50)
        
        model_file = f"{model_file_prefix}_{current_time.strftime('%Y%m%d')}.zip"
        log_folder = os.path.join(self.model_path, 'ppo_stock_tensorboard')
        train_env = DummyVecEnv([lambda: StockTradingEnv(ohlcv_data_train, window_size=self.window_size)])
        self.model = train_model(train_env, total_timesteps=20000, log_path=log_folder)
        self.model.save(model_file)

    def _core(self, ohlcv_history: List[Ohlcv]):
        self.prepare_model()

        env = StockTradingEnv(ohlcv_history)
        obs, _ = env.reset()
        action, _ = self.model.predict(obs)
        if action == 1 and self.free_money > 0:
            self.buy(spent=self.free_money)
        elif action == 2 and self.hold_amount > 0:
            self.sell(self.hold_amount)
    
if __name__ == '__main__':
    s = RlStrategy()
    s.back_test(
        start_time=datetime(2025, 3, 3),
        end_time=datetime(2025,3,5),
        investment=100000,
        symbol='TRB/USDT',
        frame='1h',
        name='TRB/USDT强化学习策略回测',
    )