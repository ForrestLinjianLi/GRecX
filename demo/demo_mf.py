# coding = utf8

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "4"
import tensorflow as tf
import numpy as np
from time import time

from grecx.datasets.light_gcn_dataset import LightGCNDataset
from grecx.datasets import LightGCNYelpDataset, LightGCNGowallaDataset, LightGCNAmazonbookDataset
from grecx.evaluation.ranking import evaluate_mean_global_metrics
from grecx.layers import UserItemEmbedding
from grecx.config import embedding_size
from tf_geometric.utils import tf_utils


dataset = "light_gcn_yelp"  # "light_gcn_yelp" | "light_gcn_gowalla" | "light_gcn_amazon-book"

data_dict = LightGCNDataset(dataset).load_data()

num_users = data_dict["num_users"]
num_items = data_dict["num_items"]
user_item_edges = data_dict["user_item_edges"]
train_index = data_dict["train_index"]
train_user_item_edges = user_item_edges[train_index]
train_user_items_dict = data_dict["train_user_items_dict"]
test_user_items_dict = data_dict["test_user_items_dict"]

drop_rate = 0.3
lr = 5e-3
l2 = 1e-4

epoches = 3000
batch_size = 8000

# MF model only relies on user and item embeddings
embedding_model = UserItemEmbedding(num_users, num_items, embedding_size, drop_rate=drop_rate, global_dropout=True)
optimizer = tf.keras.optimizers.Adam(learning_rate=lr)

@tf_utils.function
def train_step(batch_user_indices, batch_item_indices, batch_neg_item_indices):
    with tf.GradientTape() as tape:
        embedded_users, [embedded_items, embedded_neg_items] = \
            embedding_model([batch_user_indices, [batch_item_indices, batch_neg_item_indices]], training=True)

        pos_logits = tf.reduce_sum(embedded_users * embedded_items, axis=-1)
        neg_logits = tf.reduce_sum(embedded_users * embedded_neg_items, axis=-1)
        #
        # pos_losses = tf.nn.sigmoid_cross_entropy_with_logits(
        #     logits=pos_logits,
        #     labels=tf.ones_like(pos_logits)
        # )
        # neg_losses = tf.nn.sigmoid_cross_entropy_with_logits(
        #     logits=neg_logits,
        #     labels=tf.zeros_like(neg_logits)
        # )
        #
        # losses = pos_losses + neg_losses

        mf_losses = tf.nn.softplus(-(pos_logits - neg_logits))

        l2_vars = [var for var in tape.watched_variables() if "kernel" in var.name or "embeddings" in var.name]
        l2_losses = [tf.nn.l2_loss(var) for var in l2_vars]
        l2_loss = tf.add_n(l2_losses)

        loss = tf.reduce_sum(mf_losses) + l2_loss * l2

    vars = tape.watched_variables()
    grads = tape.gradient(loss, vars)
    optimizer.apply_gradients(zip(grads, vars))

    return loss, mf_losses, l2_loss


for epoch in range(0, epoches):

    if epoch % 20 == 0:
        print("\nEvaluation before epoch {}".format(epoch))
        mean_results_dict = evaluate_mean_global_metrics(test_user_items_dict, train_user_items_dict,
                                                         embedding_model.user_embeddings,
                                                         embedding_model.item_embeddings,
                                                         k_list=[10, 20], metrics=["precision", "recall", "ndcg"])
        for metrics_name, score in mean_results_dict.items():
            print("{}: {:.4f}".format(metrics_name, score))
        print()

    step_losses = []
    step_mf_losses_list = []
    step_l2_losses = []

    start_time = time()

    for step, batch_edges in enumerate(
            tf.data.Dataset.from_tensor_slices(train_user_item_edges).shuffle(1000000).batch(batch_size)):
        batch_user_indices = batch_edges[:, 0]
        batch_item_indices = batch_edges[:, 1]
        batch_neg_item_indices = np.random.randint(0, num_items, batch_item_indices.shape)

        loss, mf_losses, l2_loss = train_step(batch_user_indices, batch_item_indices, batch_neg_item_indices)

        step_losses.append(loss.numpy())
        step_mf_losses_list.append(mf_losses.numpy())
        step_l2_losses.append(l2_loss.numpy())

    end_time = time()

    if optimizer.learning_rate.numpy() > 1e-6:
        optimizer.learning_rate.assign(optimizer.learning_rate * 0.995)
        lr_status = "update lr => {:.4f}".format(optimizer.learning_rate.numpy())
    else:
        lr_status = "current lr => {:.4f}".format(optimizer.learning_rate.numpy())

    print("epoch = {}\tloss = {:.4f}\tmf_loss = {:.4f}\tl2_loss = {:.4f}\t{}\tepoch_time = {:.4f}s".format(
        epoch, np.mean(step_losses), np.mean(np.concatenate(step_mf_losses_list, axis=0)),
        np.mean(step_l2_losses), lr_status, end_time - start_time))

    if epoch == 1:
        print("the first epoch may take a long time to compile tf.function")
