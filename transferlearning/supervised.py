r"""Contains the supervised model"""
import torch
import torchvision.models as models
from torchvision.models.detection.image_list import ImageList


class TwoHeaded(torch.nn.Module):
    """With two outputs"""

    def __init__(self, input_dimension, out_dim):
        super(TwoHeaded, self).__init__()
        self._in_dim = input_dimension
        self._out_dim = out_dim
        self._cls_score, self._bbox_pred = self._init_layers()

    def _init_layers(self):
        cls = torch.nn.Linear(self._in_dim, self._out_dim)
        bbox = torch.nn.Linear(self._in_dim, self._out_dim * 4)
        return cls, bbox

    def forward(self, data):
        unscaled_probs = self._cls_score(data)
        bbox_pred = self._bbox_pred(data)
        return unscaled_probs, bbox_pred


class Supervised(torch.nn.Module):
    """Teh supervised training"""

    def __init__(self, n_dim):
        """
        The fully supervised model
        """
        super(Supervised, self).__init__()
        self._backbone, self._rpn = self._get_backbone()
        self._heads = self._get_heads(n_dim)

    def _get_backbone(self):
        """the backbone of the model
        """
        model = models.detection.maskrcnn_resnet50_fpn(pretrained=True)
        return model.backbone, model.rpn

    def _get_heads(self, out_dim):
        """The RoI heads"""
        model = models.detection.maskrcnn_resnet50_fpn(pretrained=True)
        # == custom == #
        box_pred = TwoHeaded(1024, out_dim)
        mask_predictor = models.detection.mask_rcnn.MaskRCNNPredictor(
            model.roi_heads.mask_predictor.conv5_mask.in_channels, 256,
            out_dim)

        roi_heads = models.detection.roi_heads.RoIHeads(
            box_roi_pool=model.roi_heads.box_roi_pool,
            box_head=model.roi_heads.box_head,
            box_predictor=box_pred,
            fg_iou_thresh=0.5,
            bg_iou_thresh=0.5,
            batch_size_per_image=512,
            positive_fraction=0.25,
            bbox_reg_weights=None,
            score_thresh=0.05,
            nms_thresh=0.5,
            detections_per_img=100,
            mask_roi_pool=model.roi_heads.mask_roi_pool,
            mask_head=model.roi_heads.mask_head,
            mask_predictor=mask_predictor)
        return roi_heads

    # TODO: A pre- and postprocessing
    def forward(self, img, target=None):
        if self.training:
            self._backbone.train()
            self._rpn.train()
            self._heads.train()
        else:
            self._backbone.eval()
            self._rpn.eval()
            self._heads.eval()
        target = [target] if target else None
        base = self._backbone(img)
        img_shapes = [(img.shape[2], img.shape[3])]
        img_list = ImageList(img, img_shapes)
        rois, loss_dict = self._rpn(img_list, base, target)
        result, loss_dict_head = self._heads(base, rois, img_shapes, target)
        if self.training:
            loss_dict.update(loss_dict_head)
            return loss_dict
        return result
