import torch
import torch.nn as nn
from encoders.pretrained_transformers.span_reprs import get_span_module


class SRLModel(nn.Module):
    def __init__(self, encoder,
                 span_dim=256, pool_method='avg', num_labels=1, just_last_layer=False,
                 **kwargs):
        super(SRLModel, self).__init__()
        self.encoder = encoder
        self.just_last_layer = just_last_layer
        self.pool_method = pool_method
        self.num_spans = 2
        self.span_net = nn.ModuleDict()

        self.span_net['0'] = get_span_module(
            method=pool_method, input_dim=self.encoder.hidden_size,
            use_proj=True, proj_dim=span_dim)
        self.span_net['1'] = get_span_module(
            method=pool_method, input_dim=self.encoder.hidden_size,
            use_proj=True, proj_dim=span_dim)

        self.pooled_dim = self.span_net['0'].get_output_dim()

        self.label_net = nn.Sequential(
            nn.Linear(2 * self.pooled_dim, span_dim),
            nn.Tanh(),
            nn.LayerNorm(span_dim),
            nn.Dropout(0.2),
            nn.Linear(span_dim, num_labels),
            nn.Sigmoid()
        )

        self.training_criterion = nn.BCELoss()

    def get_other_params(self):
        core_encoder_param_names = set()
        for name, param in self.encoder.model.named_parameters():
            if param.requires_grad:
                core_encoder_param_names.add(name)

        other_params = []
        print("\nParams outside core transformer params:\n")
        for name, param in self.named_parameters():
            if param.requires_grad:
                print(name, param.data.size())
                other_params.append(param)
        print("\n")
        return other_params

    def get_core_params(self):
        return self.encoder.model.parameters()

    def calc_span_repr(self, encoded_input, span_indices, index='0'):
        span_start, span_end = span_indices[:, 0], span_indices[:, 1]
        span_repr = self.span_net[index](encoded_input, span_start, span_end)

        return span_repr

    def forward(self, batch_data):
        text, text_len = batch_data.text
        encoded_input = self.encoder(text.cuda(), just_last_layer=self.just_last_layer)

        s1_repr = self.calc_span_repr(encoded_input, batch_data.span1.cuda(), index='0')
        s2_repr = self.calc_span_repr(encoded_input, batch_data.span2.cuda(), index='1')

        pred_label = self.label_net(torch.cat([s1_repr, s2_repr], dim=-1))
        pred_label = torch.squeeze(pred_label, dim=-1)

        label = torch.zeros_like(pred_label)
        label.scatter_(1, batch_data.label.cuda().unsqueeze(dim=1), 1)
        label = label.cuda().float()
        loss = self.training_criterion(pred_label, label)
        if self.training:
            return loss
        else:
            return loss, pred_label, label
