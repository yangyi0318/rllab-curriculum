# for Ant, use a small step size and vary CGI
# observe whether higher CGI leads to better descent directions
# (it should because of the analysis of NPG)

from rllab.algos.trpo import TRPO
from rllab.algos.vpg import VPG
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from rllab.baselines.zero_baseline import ZeroBaseline
from rllab.envs.normalized_env import normalize
from rllab.policies.gaussian_mlp_policy import GaussianMLPPolicy
from rllab.misc.instrument import stub, run_experiment_lite
from rllab import config
from rllab.regressors.gaussian_mlp_regressor import GaussianMLPRegressor
from rllab.optimizers.lbfgs_optimizer import LbfgsOptimizer
import lasagne.nonlinearities as NL
import lasagne
import sys
import numpy as np
import os
import itertools

from rllab.envs.mujoco.walker2d_env import Walker2DEnv
from rllab.envs.mujoco.hopper_env import HopperEnv
from rllab.envs.mujoco.half_cheetah_env import HalfCheetahEnv
from rllab.envs.mujoco.swimmer_env import SwimmerEnv
from rllab.envs.mujoco.ant_env import AntEnv
from rllab.envs.mujoco.simple_humanoid_env import SimpleHumanoidEnv

from rllab.envs.box2d.car_parking_env import CarParkingEnv
from rllab.envs.box2d.cartpole_swingup_env import CartpoleSwingupEnv
from rllab.envs.box2d.mountain_car_env import MountainCarEnv
from rllab.envs.box2d.cartpole_env import CartpoleEnv
from rllab.envs.box2d.double_pendulum_env import DoublePendulumEnv

stub(globals())
os.path.join(config.PROJECT_PATH)


# some important hyper-params that show up in the folder name -----------------
mode="ec2"
exp_prefix="trpo_cg"

algo_type = "trpo"
max_path_length=500
hidden_sizes = (32,32)
cg_init_from_prev= False
subsample_factor = 1.0
momentum = 0

cg_iters_list = [0,10,100,500]
env_names = ["ant","human"]
step_size_list = [0.001]
batch_size_list = np.array([2]) * 1000
n_itr_list = [20000]

# seeds
n_seed=10
seeds=np.arange(1,100*n_seed+1,100)

# mode settings
if mode == "local":
    n_parallel = 1
    plot = True
elif mode == "ec2":
    n_parallel = 1
    plot = False
elif mode == "ec2_parallel":
    n_parallel = 10
    config.AWS_INSTANCE_TYPE = "m4.10xlarge"
    config.AWS_SPOT_PRICE = '1.0'
    plot = False
else:
    raise NotImplementedError

# ------------------------------------------------------------------------------
exp_names = []

for env_name,cg_iters in itertools.product(env_names,cg_iters_list):
    for batch_size,step_size,n_itr in \
        zip(batch_size_list,step_size_list,n_itr_list):
        assert(np.mod(batch_size,1000)==0)
        if env_name == "swimmer":
            env = SwimmerEnv()
        elif env_name == "hopper":
            env = HopperEnv()
        elif env_name == "halfcheetah":
            env = HalfCheetahEnv()
        elif env_name == "walker":
            env = Walker2DEnv()
        elif env_name == "car_parking":
            env = CarParkingEnv()
        elif env_name == "cartpole_swingup":
            env = CartpoleSwingupEnv()
        elif env_name == "mountain_car":
            env = MountainCarEnv()
        elif env_name in ["double_pendulum","dpend"]:
            env = DoublePendulumEnv()
        elif env_name == "cartpole":
            env = CartpoleEnv()
        elif env_name == "ant":
            env = AntEnv()
        elif env_name == "human":
            env = SimpleHumanoidEnv()
        else:
            raise NotImplementedError
        env = normalize(env)

        policy = GaussianMLPPolicy(
            init_std=1.0,
            env_spec=env.spec,
            hidden_sizes=hidden_sizes,
        )

        baseline = LinearFeatureBaseline(env_spec=env.spec)
        # baseline = ZeroBaseline(env_spec=env.spec)


        if algo_type == "trpo":
            algo = TRPO(
                env=env,
                policy=policy,
                baseline=baseline,
                batch_size=batch_size,
                max_path_length=max_path_length,
                n_itr=n_itr,
                discount=0.99,
                step_size=step_size,
                plot=plot,
                store_paths=True,

                optimizer_args=dict(
                    cg_iters=cg_iters,
                    cg_init_from_prev=cg_init_from_prev,
                    subsample_factor=subsample_factor,
                    momentum=momentum,
                )
            )

        import datetime
        import dateutil.tz
        now = datetime.datetime.now(dateutil.tz.tzlocal())
        timestamp = now.strftime('%Y%m%d_%H%M%S')



        # so hard to find a short name
        nn_spec = "nn"
        for size in hidden_sizes:
            nn_spec += "_%d"%(size)

        exp_name_prefix="alex_{time}_{env_name}_cgi{cg_iters}_m{momentum}_sf_{subsample_factor}_kl{step_size}_bs{batch_size}k".format(
            time=timestamp,
            env_name=env_name,
            cg_iters=cg_iters,
            momentum=momentum,
            subsample_factor=subsample_factor,
            step_size=step_size,
            batch_size=batch_size/1000,
        )
        exp_names.append("\"" + exp_name_prefix + "\",")

        for seed in seeds:
            exp_name = exp_name_prefix + "_s%d"%(seed)
            if mode=="local":
                def run():
                    run_experiment_lite(
                        algo.train(),
                        exp_prefix=exp_prefix,
                        n_parallel=n_parallel,
                        snapshot_mode="all",
                        seed=seed,
                        plot=plot,
                        exp_name=exp_name,
                    )
            elif (mode=="ec2") or (mode=="ec2_parallel"):
                if len(exp_name) > 64:
                    print "Should not use experiment name with length %d > 64.\nThe experiment name is %s.\n Exit now."%(len(exp_name),exp_name)
                    sys.exit(1)
                def run():
                    run_experiment_lite(
                        algo.train(),
                        exp_prefix=exp_prefix,
                        n_parallel=n_parallel,
                        snapshot_mode="all",
                        seed=seed,
                        plot=plot,
                        exp_name=exp_name,

                        mode="ec2",
                        terminate_machine=True,
                    )
            else:
                raise NotImplementedError
            run()


# record the experiment names to a file
# also record the branch name and commit number
logs = []
git_commit_log = "git_commit_log"
os.system("git log > %s"%(git_commit_log))
with open(git_commit_log,"r") as f:
    cur_commit_line = f.readlines()[0]
    logs.append(cur_commit_line)

git_branch_log = "git_branch_log"
os.system("git branch > %s"%(git_branch_log))
with open(git_branch_log,"r") as f:
    for line in f.readlines():
        if "*" in line:
            branch = line.split('* ')[1]
            logs.append(branch)
            break

logs += exp_names
cur_script_name = __file__
log_file_name = cur_script_name.split('.py')[0] + '.log'
with open(log_file_name,'w') as f:
    for message in logs:
        f.write(message + "\n")

# make the current script read-only to avoid accidental changes
os.system("chmod 444 %s"%(__file__))
