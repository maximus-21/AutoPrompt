from utils.llm_chain import ChainWrapper, set_callbck
from dataset.base_dataset import DatasetBase
import pandas as pd
from agent.meta_agent import load_tools
from agent.agent_utils import build_agent, batch_invoke
from utils.config import get_llm

class AgentEstimator:
    """
    A wrapper for an estimator of agent
    """

    def __init__(self, opt):
        """
        Initialize a new instance of the LLMEstimator class.
        :param opt: The configuration file (EasyDict)
        """
        self.opt = opt
        self.chain = None
        self.mini_batch_size = opt.mini_batch_size
        self.mode = opt.mode
        self.num_workers = opt.num_workers
        self.usage_callback = set_callbck(opt.llm.type)
        self.agent = None
        if 'instruction' in opt.keys():
            self.cur_instruct = opt.instruction
        else:
            self.cur_instruct = None
        self.tools = load_tools(opt.tools_path)
        self.llm = get_llm(opt.llm)
        self.chain_yaml_extraction = ChainWrapper(opt.llm, 'prompts/meta_prompts_agent/extract_yaml.prompt', None, None)
        self.total_usage = 0
    def calc_usage(self) -> float:
        """"
        Calculate the usage of the estimator
        """
        return self.total_usage

    def apply_dataframe(self, record: pd.DataFrame):
        """
        Apply the estimator on a dataframe
        :param record: The record
        """
        batch_inputs = []
        # prepare all the inputs for the chains
        for i, row in record.iterrows():
            batch_inputs.append({'input': row['text']})
        all_results = batch_invoke(self.agent, batch_inputs, self.num_workers, self.usage_callback)
        self.total_usage += sum([res['usage'] for res in all_results])
        for res in all_results:
            record.loc[res['index'], self.mode] = res['result']['output']
        return record

    def apply(self, dataset: DatasetBase, idx: int, leq: bool = False):
        """
        Apply the estimator on the batches up to idx (includes), it then updates the annotation field
        if self.mode is 'annotation', otherwise it update the prediction field.
        :param dataset: The dataset
        :param idx: The current batch index
        :param leq: If True, apply on all the batches up to idx (includes), otherwise apply only on idx
        """

        self.agent = build_agent(self.llm, self.tools, self.chain_yaml_extraction,
                                 self.cur_instruct, intermediate_steps=True)

        if leq:
            batch_records = dataset.get_leq(idx)
        else:
            batch_records = dataset[idx]
        return self.apply_dataframe(batch_records)