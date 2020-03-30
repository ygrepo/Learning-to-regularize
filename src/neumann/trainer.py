import time

import torch
import torch.nn as nn

from src.neumann.utils import SAVE_LOAD_TYPE, MODEL, save_model, load_model, isclose


class Trainer(nn.Module):
    def __init__(self, model_name, model, optimizer, criterion,
                 train_dataloader, test_dataloader, run_id, config):
        super(Trainer, self).__init__()
        self.model_name = model_name
        self.model = model.to(config["device"])
        self.config = config
        self.training_data_loader = train_dataloader
        self.test_data_loader = test_dataloader
        self.optimizer = optimizer
        self.criterion = criterion
        self.epochs = 0
        self.max_epochs = config["num_of_train_epochs"]
        self.run_id = str(run_id)
        self.add_run_id = config["add_run_id"]

    def train_epochs(self):
        best_acc = 0  # best test accuracy
        start_epoch = 0
        max_loss = 1e8
        max_loss_repeat = 4
        loss_repeat_counter = 1
        prev_loss = float("-inf")

        if self.config["reload_model"] == SAVE_LOAD_TYPE.MODEL:
            _, _, best_acc, start_epoch = load_model(self.model_name, self.model, self.optimizer)

        start_time = time.time()
        for epoch in range(start_epoch, start_epoch + self.max_epochs):

            self.train(epoch)
            test_loss, acc = self.test(epoch)

            # Save checkpoint.
            if self.model_name == MODEL.neumann:
                if test_loss < max_loss:
                    print("Loss decreased, saving model!")
                    save_model(self.model_name, self.model, self.optimizer, acc, epoch)
                    max_loss = test_loss
                if isclose(test_loss, prev_loss, rel_tol=1e-4):
                    loss_repeat_counter += 1
                    if loss_repeat_counter >= max_loss_repeat:
                        print(f"Test loss not decreasing for last {loss_repeat_counter} times")
                        break
                    else:
                        loss_repeat_counter += 1

            if self.model_name != MODEL.neumann and acc > best_acc:
                best_acc = acc
                save_model(self.model_name, self.model, self.optimizer, acc, epoch)

        print("Total Training in mins: %5.2f" % ((time.time() - start_time) / 60))

    def train(self, epoch):
        self.model.train()
        running_loss = 0
        total_loss = 0
        total = 0
        correct = 0
        for batch_num, data in enumerate(self.training_data_loader):
            loss, total, correct = self.train_batch(total, correct, data)
            running_loss += loss.item()
            total_loss += running_loss

            if batch_num % 100 == 99:  # print every 2000 mini-batches
                print("[TRAINING] epoch:{:d}, batch:{:d}, loss:{:8.4f}, acc:{:.3f}, ({:d}/{:d})"
                      .format(epoch + 1, batch_num + 1, running_loss / (batch_num + 1), 100. * correct / total, correct,
                              total))
                running_loss = 0.0

        return total_loss

    def train_batch(self, total, correct, data):
        # get the inputs; data is a list of [inputs, labels]
        inputs, targets = data
        inputs, targets = inputs.to(self.config["device"]), targets.to(self.config["device"])

        self.optimizer.zero_grad()
        outputs = self.model(inputs)
        loss = self.criterion(outputs, targets)
        loss.backward()
        self.optimizer.step()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()
        return loss, total, correct

    def test(self, epoch):
        self.model.eval()
        test_loss = 0
        total_loss = 0
        correct = 0
        total = 0
        with torch.no_grad():
            for batch_num, (inputs, targets) in enumerate(self.test_data_loader):
                inputs, targets = inputs.to(self.config["device"]), targets.to(self.config["device"])
                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)

                test_loss += loss.item()
                total_loss += test_loss

                if self.config["model"] == MODEL.neumann:
                    continue

                _, predicted = outputs.max(1)
                total += targets.size(0)
                correct += predicted.eq(targets).sum().item()
                if batch_num % 100 == 99:  # print every 2000 mini-batches
                    print("[TESTING] epoch:{:d}, batch:{:d}, loss:{:8.4f}, acc:{:.3f}, ({:d}/{:d})"
                          .format(epoch + 1, batch_num + 1, test_loss / (batch_num + 1), 100. * correct / total,
                                  correct, total))

                    test_loss = 0.0

        if total == 0:
            return total_loss, 0

        return total_loss, 100. * correct / total