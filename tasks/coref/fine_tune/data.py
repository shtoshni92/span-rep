from torchtext.data import Example, Field, Dataset
import torchtext.data as data
import json
import os


class CorefDataset(Dataset):
    """Class for parsing the Ontonotes coref dataset."""

    def __init__(self, path, model, train_frac=1.0,
                 encoding="utf-8", separator="\t",
                 max_seq_len=512):
        text_field = Field(sequential=True, use_vocab=False, include_lengths=True,
                           batch_first=True, pad_token=model.tokenizer.pad_token_id)
        non_seq_field = Field(sequential=False, use_vocab=False, batch_first=True)
        fields = [('text', text_field),
                  ('span1', non_seq_field),
                  ('orig_span1', non_seq_field),
                  ('span2', non_seq_field),
                  ('orig_span2', non_seq_field),
                  ('label', non_seq_field)]

        examples = []
        f = open(path, encoding=encoding)
        lines = f.readlines()
        is_train = self.check_for_train_file(path)

        # if True:
        if is_train and train_frac < 1.0:
            red_num_lines = int(len(lines) * train_frac)
            lines = lines[:red_num_lines]

        for line in lines:
            instance = json.loads(line)
            text, subword_to_word_idx = model.tokenize(
                instance["text"].split(), get_subword_indices=True)

            for target in instance["targets"]:
                span1_index = self.get_tokenized_span_indices(
                    subword_to_word_idx, target["span1"])
                span2_index = self.get_tokenized_span_indices(
                    subword_to_word_idx, target["span2"])
                label = target["label"]
                examples.append(
                    Example.fromlist([text, span1_index, target["span1"], span2_index,
                                      target["span2"], label], fields))

        super(CorefDataset, self).__init__(examples, fields)

    def check_for_train_file(self, file_path):
        if os.path.basename(file_path) == "train.json":
            return True
        return False

    @staticmethod
    def get_tokenized_span_indices(subword_to_word_idx, orig_span_indices):
        orig_start_idx, orig_end_idx = orig_span_indices
        start_idx = subword_to_word_idx.index(orig_start_idx)
        # Search for the index of the last subword
        end_idx = len(subword_to_word_idx) - 1 - subword_to_word_idx[::-1].index(orig_end_idx - 1)
        return [start_idx, end_idx]

    @staticmethod
    def sort_key(example):
        return len(example.text)

    @classmethod
    def iters(cls, path, model, batch_size=32, eval_batch_size=32, train_frac=1.0):
        train, val, test = CorefDataset.splits(
            path=path, train='train.json', validation='development.json', test='test.json',
            model=model, train_frac=train_frac)

        train_iter = data.BucketIterator(
            train, batch_size=batch_size,
            sort_within_batch=True, shuffle=True, repeat=False)

        val_iter, test_iter = data.BucketIterator.splits(
            (val, test), batch_size=eval_batch_size,
            sort_within_batch=True, shuffle=False, repeat=False)

        return (train_iter, val_iter, test_iter)


if __name__ == '__main__':
    from encoders.pretrained_transformers import Encoder
    encoder = Encoder(cased=False)
    path = "/home/shtoshni/Research/hackathon_2019/tasks/coref/data"
    train_iter, val_iter, test_iter = CorefDataset.iters(path, encoder, train_frac=1.0)

    print("Train size:", len(train_iter.data()))
    print("Val size:", len(val_iter.data()))
    print("Test size:", len(test_iter.data()))

    for batch_data in train_iter:
        print(batch_data.text[0].shape)
        print(batch_data.span1.shape)
        print(batch_data.span2.shape)
        print(batch_data.label.shape)

        text, text_len = batch_data.text
        text_ids = text[0, :text_len[0]].tolist()

        itos = encoder.tokenizer.ids_to_tokens
        sent_tokens = [itos[text_id] for text_id in text_ids]
        sent = ' '.join(sent_tokens)
        span1 = ' '.join(sent_tokens[batch_data.span1[0, 0]:batch_data.span1[0, 1] + 1])
        print(sent)
        print(batch_data.span1[0, :])
        print(span1)
        break
